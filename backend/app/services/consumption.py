"""Durable, atomic admission limits for one deployment sharing DATA_DIR.

Stores counters and expiring leases, never prompts, answers or raw IP addresses.
SQLite coordinates threads/processes on the same local volume. Separate replicas
must use separate budgets or an upstream shared limiter, not independent copies
of the same allowance.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class LimitExceeded(Exception):
    def __init__(self, reason: str, retry_after: int = 60):
        self.reason = reason
        self.retry_after = retry_after
        super().__init__(reason)


class ConsumptionGuard:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_dir / "usage.sqlite3"
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        with self._transaction() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS metadata (name TEXT PRIMARY KEY, value BLOB NOT NULL)"
            )
            db.execute(
                "INSERT OR IGNORE INTO metadata VALUES('peer_salt', ?)",
                (secrets.token_bytes(32),),
            )
            self.salt = db.execute(
                "SELECT value FROM metadata WHERE name='peer_salt'"
            ).fetchone()[0]
            db.execute(
                "CREATE TABLE IF NOT EXISTS counters (name TEXT, window INTEGER, value INTEGER NOT NULL, expires REAL NOT NULL, PRIMARY KEY(name, window))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS leases (id TEXT PRIMARY KEY, expires REAL NOT NULL)"
            )
        os.chmod(self.path, 0o600)

    @contextmanager
    def _transaction(self):
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            db.execute("PRAGMA busy_timeout=5000")
            db.execute("PRAGMA trusted_schema=OFF")
            if hasattr(db, "enable_load_extension"):
                db.enable_load_extension(False)
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _charge(db, entries, now):
        # Validate all counters before mutating any: rejected calls cost nothing.
        for name, window, amount, limit, expiry in entries:
            row = db.execute(
                "SELECT value FROM counters WHERE name=? AND window=?", (name, window)
            ).fetchone()
            if (row[0] if row else 0) + amount > limit:
                raise LimitExceeded(name.split(":")[0], max(1, int(expiry - now)))
        for name, window, amount, limit, expiry in entries:
            db.execute(
                "INSERT INTO counters VALUES(?,?,?,?) ON CONFLICT(name,window) DO UPDATE SET value=value+excluded.value",
                (name, window, amount, expiry),
            )

    def admit_chat(self, client: str) -> str:
        now = time.time()
        minute, day = int(now // 60), int(now // 86400)
        peer = hmac.new(self.salt, client.encode(), hashlib.sha256).hexdigest()
        with self._transaction() as db:
            db.execute("DELETE FROM counters WHERE expires < ?", (now,))
            db.execute("DELETE FROM leases WHERE expires < ?", (now,))
            if (
                db.execute("SELECT count(*) FROM leases").fetchone()[0]
                >= self.settings.chat_concurrency_limit
            ):
                raise LimitExceeded("concurrency", 2)
            self._charge(
                db,
                [
                    (
                        f"client:{peer}",
                        minute,
                        1,
                        self.settings.chat_requests_per_minute,
                        (minute + 1) * 60,
                    ),
                    (
                        "chat_daily",
                        day,
                        1,
                        self.settings.chat_requests_per_day,
                        (day + 1) * 86400,
                    ),
                ],
                now,
            )
            lease = secrets.token_hex(16)
            db.execute(
                "INSERT INTO leases VALUES(?,?)",
                (
                    lease,
                    now
                    + self.settings.chat_timeout_seconds
                    + self.settings.request_read_timeout_seconds
                    + 10,
                ),
            )
            return lease

    def release_chat(self, lease: str):
        with self._transaction() as db:
            db.execute("DELETE FROM leases WHERE id=?", (lease,))

    def reserve_provider_call(self, output_tokens: int):
        now = time.time()
        day = int(now // 86400)
        with self._transaction() as db:
            self._charge(
                db,
                [
                    (
                        "provider_daily_calls",
                        day,
                        1,
                        self.settings.provider_calls_per_day,
                        (day + 1) * 86400,
                    ),
                    (
                        "provider_daily_output",
                        day,
                        output_tokens,
                        self.settings.provider_output_tokens_per_day,
                        (day + 1) * 86400,
                    ),
                ],
                now,
            )
