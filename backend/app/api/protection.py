"""ASGI boundary limits; applied before FastAPI parses request JSON."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from html.parser import HTMLParser
from pathlib import Path

from starlette.concurrency import run_in_threadpool
from ..services.consumption import LimitExceeded

logger = logging.getLogger(__name__)


class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.inline = False
        self.parts = []
        self.hashes = set()

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.inline = not dict(attrs).get("src")
            self.parts = []

    def handle_data(self, data):
        if self.inline:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.inline:
            digest = hashlib.sha256("".join(self.parts).encode()).digest()
            self.hashes.add("'sha256-" + base64.b64encode(digest).decode() + "'")
            self.inline = False


def content_security_policy(static_dir: Path) -> str:
    scripts = _Scripts()
    for html in static_dir.rglob("*.html"):
        scripts.feed(html.read_text(encoding="utf-8"))
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self' " + " ".join(sorted(scripts.hashes)),
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "connect-src 'self'",
            "object-src 'none'",
            "base-uri 'none'",
            "frame-ancestors 'none'",
            "form-action 'self'",
        ]
    )


class ProtectionMiddleware:
    def __init__(self, app, settings, static_dir):
        self.app = app
        self.settings = settings
        self.csp = content_security_policy(static_dir)
        self._release_tasks = set()

    def _authorized(self, headers):
        if not self.settings.app_access_password:
            return True
        try:
            auth = headers.get(b"authorization", b"")
            if len(auth) > 1024:
                return False
            scheme, encoded = auth.split(b" ", 1)
            if scheme.lower() != b"basic":
                return False
            supplied = base64.b64decode(encoded, validate=True)
            expected = f"{self.settings.app_access_username}:{self.settings.app_access_password}".encode()
            return hmac.compare_digest(supplied, expected)
        except (ValueError, TypeError):
            return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def secured_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                        (b"referrer-policy", b"no-referrer"),
                        (
                            b"permissions-policy",
                            b"camera=(), microphone=(), geolocation=()",
                        ),
                        (b"content-security-policy", self.csp.encode()),
                    ]
                )
                if scope.get("scheme") == "https":
                    headers.append((b"strict-transport-security", b"max-age=31536000"))
                if (
                    scope["path"].startswith("/api/")
                    or self.settings.app_access_password
                ):
                    headers.append((b"cache-control", b"no-store"))
                message = {**message, "headers": headers}
            await send(message)

        async def error(status, detail, extra=()):
            body = json.dumps({"detail": detail}).encode()
            await secured_send(
                {
                    "type": "http.response.start",
                    "status": status,
                    "headers": [(b"content-type", b"application/json"), *extra],
                }
            )
            await secured_send({"type": "http.response.body", "body": body})

        headers = dict(scope.get("headers", []))
        if scope["path"] != "/api/health" and not self._authorized(headers):
            return await error(
                401,
                "Authentication required",
                [(b"www-authenticate", b'Basic realm="InsureTutor", charset="UTF-8"')],
            )
        if scope["path"] not in {"/api/chat", "/api/brochures"} or scope["method"] != "POST":
            return await self.app(scope, receive, secured_send)
        body_limit = (self.settings.max_brochure_upload_bytes
                      if scope["path"] == "/api/brochures" else self.settings.max_request_bytes)
        guard = scope["app"].state.consumption
        admission = None
        try:
            length = headers.get(b"content-length")
            if length is not None:
                try:
                    size = int(length)
                except ValueError:
                    return await error(400, "Invalid Content-Length")
                if size < 0:
                    return await error(400, "Invalid Content-Length")
                if size > body_limit:
                    return await error(413, "Request body is too large")
            # Uses ASGI peer, never an arbitrary request's X-Forwarded-For.
            # Configure trusted proxies at the server, not in application headers.
            peer = (scope.get("client") or ("unknown",))[0]
            # A canceled thread await does not stop SQLite from committing.
            # Keep its result available to cleanup even if this request leaves.
            admission = asyncio.create_task(run_in_threadpool(guard.admit_chat, peer))
            await asyncio.shield(admission)
            body = bytearray()
            async with asyncio.timeout(self.settings.request_read_timeout_seconds):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > body_limit:
                        return await error(413, "Request body is too large")
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
            delivered = False
            disconnected = asyncio.Event()

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {
                        "type": "http.request",
                        "body": bytes(body),
                        "more_body": False,
                    }
                await disconnected.wait()
                return {"type": "http.disconnect"}

            async def watch_disconnect():
                while True:
                    if (await receive())["type"] == "http.disconnect":
                        disconnected.set()
                        return

            async with asyncio.timeout(self.settings.chat_timeout_seconds):
                work = asyncio.create_task(self.app(scope, replay, secured_send))
                disconnect = asyncio.create_task(watch_disconnect())
                try:
                    done, _ = await asyncio.wait(
                        (work, disconnect), return_when=asyncio.FIRST_COMPLETED
                    )
                    if work in done:
                        await work
                    else:
                        await disconnect
                finally:
                    for task in (work, disconnect):
                        if not task.done():
                            task.cancel()
                    # Await cancellation so the provider closes its connection
                    # before releasing this request's concurrency allowance.
                    await asyncio.gather(work, disconnect, return_exceptions=True)
        except LimitExceeded as exc:
            await error(
                429,
                "Request allowance reached. Please try again later.",
                [(b"retry-after", str(exc.retry_after).encode())],
            )
        except TimeoutError:
            if not started:
                await error(504, "The request timed out. Please try again.")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("Chat boundary failed", exc_info=False)
            if not started:
                await error(503, "The service is temporarily unavailable")
        finally:
            if admission is not None:
                async def release_admitted():
                    try:
                        lease = await admission
                    except Exception:
                        return  # Admission failed without creating a lease.
                    try:
                        await run_in_threadpool(guard.release_chat, lease)
                    except Exception:
                        logger.error("Could not release chat lease; it will expire")

                cleanup = asyncio.create_task(release_admitted())
                # Retain cleanup if repeated cancellation interrupts the shield.
                self._release_tasks.add(cleanup)
                cleanup.add_done_callback(self._release_tasks.discard)
                await asyncio.shield(cleanup)
