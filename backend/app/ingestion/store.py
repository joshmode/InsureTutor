from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from ..config import Settings
from .chunker import Chunk, chunk_document

logger = logging.getLogger(__name__)
SCHEMA_VERSION = 5


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.chunks: list[Chunk] = []
        self.manifest_path = settings.data_dir / "chunks.json"

    def _sources(self) -> dict[str, Path]:
        root = self.settings.knowledge_base_dir.resolve()
        sources = {}
        for name in self.settings.document_names:
            # Config is trusted, but a typo must never expose another file via
            # ingestion or turn a symlink into access outside the corpus.
            if Path(name).name != name or Path(name).suffix.lower() != ".pdf":
                raise ValueError(
                    "DOCUMENTS must contain PDF filenames within the knowledge directory"
                )
            path = (root / name).resolve()
            if not path.is_relative_to(root):
                raise ValueError("Knowledge document escapes the knowledge directory")
            if not path.is_file():
                raise FileNotFoundError(f"Knowledge document not found: {name}")
            sources[name] = path
        return sources

    def _fingerprints(self) -> dict[str, str]:
        return {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in self._sources().items()
        }

    def ingest(self) -> list[Chunk]:
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        all_chunks: list[Chunk] = []
        sources = self._sources()
        fingerprints = self._fingerprints()
        for name, path in sources.items():
            document_chunks = chunk_document(path)
            if any(c.source_sha256 != fingerprints[name] for c in document_chunks):
                raise ValueError(
                    "Source changed during ingestion; retry with a stable corpus"
                )
            logger.info("Ingested %s into %d chunks", name, len(document_chunks))
            all_chunks.extend(document_chunks)
        self.chunks = list({chunk.id: chunk for chunk in all_chunks}.values())
        payload = {
            "schema_version": SCHEMA_VERSION,
            "source_fingerprints": fingerprints,
            "chunks": [asdict(chunk) for chunk in self.chunks],
        }
        # Unique temporary paths make simultaneous worker startup safe.
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.settings.data_dir,
                prefix="chunks-",
                suffix=".tmp",
                delete=False,
            ) as handle:
                tmp = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            tmp.replace(self.manifest_path)
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
        return self.chunks

    def load(self) -> list[Chunk]:
        if not self.manifest_path.exists():
            return self.ingest()
        raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        fingerprints = self._fingerprints()
        if (
            not isinstance(raw, dict)
            or raw.get("schema_version") != SCHEMA_VERSION
            or raw.get("source_fingerprints") != fingerprints
        ):
            return self.ingest()
        self.chunks = [Chunk(**item) for item in raw["chunks"]]
        if not self.chunks or any(
            c.source_sha256 not in fingerprints.values() for c in self.chunks
        ):
            return self.ingest()
        return self.chunks

    def ensure_ready(self) -> list[Chunk]:
        if self.settings.ingest_on_startup or not self.manifest_path.exists():
            return self.ingest()
        try:
            return self.load()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "Could not load chunk manifest (%s); rebuilding", type(exc).__name__
            )
            return self.ingest()
