"""Private, bounded document contexts sharing one verified embedding model."""
from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from ..chat.orchestrator import ChatOrchestrator
from ..ingestion.chunker import Chunk
from ..models import BrochureInfo
from ..retrieval.hybrid import HybridRetriever

OWNER_COOKIE = "insuretutor_upload_owner"


class BrochureError(ValueError):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass
class BrochureContext:
    info: BrochureInfo
    path: Path
    owner_hash: str
    retriever: HybridRetriever
    orchestrator: ChatOrchestrator


class BrochureStore:
    def __init__(self, settings, llm, embedding_backend):
        self.settings = settings
        self.llm = llm
        self.backend = embedding_backend
        self.root = settings.data_dir / "private-brochures"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.preparation_lock = threading.Lock()
        self.contexts: dict[str, BrochureContext] = {}
        self.prune()

    def prune(self):
        with self._locked():
            self._cleanup()

    @contextmanager
    def _locked(self):
        with self.lock, (self.root / ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    @staticmethod
    def _owner(owner: str) -> str:
        return hashlib.sha256(owner.encode()).hexdigest()

    def _cleanup(self):
        now = time.time()
        # Other workers can delete an owned record; release this worker's
        # in-memory vectors too instead of retaining unreachable contexts.
        for identifier in list(self.contexts):
            if not (self.root / identifier / "metadata.json").is_file():
                self.contexts.pop(identifier, None)
        for directory in self.root.iterdir():
            if not directory.is_dir() or not re.fullmatch(r"[a-f0-9]{32}", directory.name):
                continue
            metadata = directory / "metadata.json"
            # A crashed worker's incomplete reservation expires too.
            expiry = directory.stat().st_mtime + self.settings.brochure_retention_seconds
            if metadata.exists():
                try:
                    expiry = json.loads(metadata.read_text())["expires_at"]
                except (ValueError, KeyError):
                    pass
            if expiry <= now:
                self.contexts.pop(directory.name, None)
                shutil.rmtree(directory)

    @contextmanager
    def _preparing(self):
        # Request cancellation cannot stop native inference in a worker thread.
        # Bound the actual work, rather than just the lifetime of its HTTP request.
        busy = "Another brochure is being prepared. Please try again shortly."
        if not self.preparation_lock.acquire(blocking=False):
            raise BrochureError(busy, 429)
        try:
            with (self.root / ".prepare.lock").open("a") as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise BrochureError(busy, 429) from None
                try:
                    yield
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)
        finally:
            self.preparation_lock.release()

    def _chunks(self, directory):
        return [Chunk(**c) for c in json.loads((directory / "chunks.json").read_text())["chunks"]]

    def _context(self, chunks, metadata):
        retriever = HybridRetriever(chunks, self.settings, embedding_backend=self.backend)
        orchestrator = ChatOrchestrator(self.settings, retriever, self.llm)
        info = BrochureInfo(**{k: metadata[k] for k in BrochureInfo.model_fields})
        info.retrieval_mode = retriever.mode
        return BrochureContext(info, self.root / info.id / "brochure.pdf", metadata["owner_hash"], retriever, orchestrator)

    def create(self, content: bytes, filename: str, owner: str) -> BrochureContext:
        with self._preparing():
            return self._create(content, filename, owner)

    def _create(self, content: bytes, filename: str, owner: str) -> BrochureContext:
        if not content.startswith(b"%PDF-") or len(content) > self.settings.max_brochure_upload_bytes:
            raise BrochureError("Upload a PDF no larger than 8 MiB.")
        filename = filename.strip()
        if (not filename.lower().endswith(".pdf") or len(filename.encode()) > 200
                or any(c in filename for c in "/\\") or any(ord(c) < 32 for c in filename)):
            raise BrochureError("Use a PDF filename without path separators (up to 200 bytes).")
        with self._locked():
            self._cleanup()
            if sum(p.is_dir() for p in self.root.iterdir()) >= self.settings.max_private_brochures:
                raise BrochureError("Document capacity is reached. Remove an uploaded brochure or try later.", 429)
            identifier = secrets.token_hex(16)
            directory = self.root / identifier
            directory.mkdir(mode=0o700)
        try:
            source = directory / "brochure.pdf"
            source.write_bytes(content)
            output = directory / "chunks.json"
            # No LLM keys, cloud secrets or proxy credentials enter the parser.
            result = subprocess.run(
                [sys.executable, "-m", "backend.app.ingestion.upload_worker", str(source.resolve()), str(output.resolve())],
                cwd=Path(__file__).resolve().parents[3],
                env={"PATH": os.defpath, "PYTHONDONTWRITEBYTECODE": "1"},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25,
            )
            if result.returncode or not output.exists():
                raise BrochureError("Could not read this PDF within processing limits. Use an unencrypted, text-based brochure with 1–100 pages (scans need OCR first).")
            data = json.loads(output.read_text())
            data["chunks"] = [dict(c, document=filename) for c in data["chunks"]]
            output.write_text(json.dumps(data))
            metadata = dict(id=identifier, filename=filename, pages=data["pages"], chunks=len(data["chunks"]),
                            retrieval_mode="pending", expires_at=time.time()+self.settings.brochure_retention_seconds,
                            owner_hash=self._owner(owner))
            context = self._context([Chunk(**c) for c in data["chunks"]], metadata)
            metadata["retrieval_mode"] = context.info.retrieval_mode
            with self._locked():
                pending = directory / "metadata.tmp"
                pending.write_text(json.dumps(metadata))
                pending.replace(directory / "metadata.json")
                self.contexts[identifier] = context
            return context
        except subprocess.TimeoutExpired:
            shutil.rmtree(directory, ignore_errors=True)
            raise BrochureError("PDF processing timed out. Try a smaller, text-based brochure.") from None
        except BaseException:
            shutil.rmtree(directory, ignore_errors=True)
            raise

    def _metadata(self, identifier: str, owner: str):
        """Read an owned record while the caller holds the storage lock."""
        self._cleanup()
        if not owner or not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise BrochureError("Brochure not found or expired. Upload it again.", 404)
        directory = self.root / identifier
        try:
            metadata = json.loads((directory / "metadata.json").read_text())
        except FileNotFoundError:
            raise BrochureError("Brochure not found or expired. Upload it again.", 404) from None
        if not hmac.compare_digest(metadata["owner_hash"], self._owner(owner)):
            raise BrochureError("Brochure not found or expired. Upload it again.", 404)
        return directory, metadata

    def source(self, identifier: str, owner: str, document: str | None = None):
        with self._locked():
            directory, metadata = self._metadata(identifier, owner)
            if document is not None and document != metadata["filename"]:
                raise BrochureError("Source document not found", 404)
            # Read before deletion/expiry can remove the owned record.
            return metadata["filename"], (directory / "brochure.pdf").read_bytes()

    def chunks(self, identifier: str, owner: str):
        with self._locked():
            directory, _ = self._metadata(identifier, owner)
            return self._chunks(directory)

    def get(self, identifier: str, owner: str) -> BrochureContext:
        with self._locked():
            self._metadata(identifier, owner)
            if identifier in self.contexts:
                return self.contexts[identifier]
        with self._preparing():
            with self._locked():
                directory, metadata = self._metadata(identifier, owner)
                chunks = self._chunks(directory)
            context = self._context(chunks, metadata)
            with self._locked():
                # It could have been deleted or expired during inference.
                self._metadata(identifier, owner)
                self.contexts[identifier] = context
                return context

    def delete(self, identifier: str, owner: str):
        with self._locked():
            # Inline ownership check rather than recursively acquiring flock.
            if not re.fullmatch(r"[a-f0-9]{32}", identifier):
                raise BrochureError("Brochure not found", 404)
            directory = self.root / identifier
            try:
                metadata = json.loads((directory / "metadata.json").read_text())
            except FileNotFoundError:
                raise BrochureError("Brochure not found", 404) from None
            if not hmac.compare_digest(metadata["owner_hash"], self._owner(owner)):
                raise BrochureError("Brochure not found", 404)
            self.contexts.pop(identifier, None)
            shutil.rmtree(directory)
