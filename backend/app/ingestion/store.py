from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import Settings
from .chunker import Chunk, chunk_document

logger = logging.getLogger(__name__)


class KnowledgeBase:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.chunks: list[Chunk] = []
        self.manifest_path = settings.data_dir / "chunks.json"

    def ingest(self) -> list[Chunk]:
        """Build a deterministic, duplicate-free chunk catalog.

        The manifest is replaced atomically, so repeated startup does not append
        duplicate records.
        """
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        all_chunks: list[Chunk] = []
        for name in self.settings.document_names:
            path = self.settings.knowledge_base_dir / name
            if not path.exists():
                raise FileNotFoundError(f"Knowledge document not found: {path}")
            document_chunks = chunk_document(path)
            logger.info("Ingested %s into %d chunks", name, len(document_chunks))
            all_chunks.extend(document_chunks)

        deduped: dict[str, Chunk] = {}
        for chunk in all_chunks:
            deduped.setdefault(chunk.id, chunk)
        self.chunks = list(deduped.values())
        tmp_path = self.manifest_path.with_suffix(".json.tmp")
        tmp_path.write_text(
            json.dumps(
                [
                    {
                        "id": c.id,
                        "document": c.document,
                        "page": c.page,
                        "section": c.section,
                        "content": c.content,
                        "content_type": c.content_type,
                        "excerpt": c.citation_excerpt,
                    }
                    for c in self.chunks
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tmp_path.replace(self.manifest_path)
        return self.chunks

    def load(self) -> list[Chunk]:
        if not self.manifest_path.exists():
            return self.ingest()
        raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.chunks = [
            Chunk(
                id=item["id"],
                document=item["document"],
                page=int(item["page"]),
                section=item["section"],
                content=item["content"],
                content_type=item.get("content_type", "prose"),
                excerpt=item.get("excerpt", ""),
            )
            for item in raw
        ]
        return self.chunks

    def ensure_ready(self) -> list[Chunk]:
        if self.settings.ingest_on_startup or not self.manifest_path.exists():
            return self.ingest()
        try:
            return self.load()
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            logger.warning("Could not load chunk manifest (%s); rebuilding", exc)
            return self.ingest()

