from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import numpy as np

from ..ingestion.chunker import Chunk

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    name: str
    available: bool

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class LocalFastEmbedBackend:
    """Local ONNX embeddings; provider-independent and optional."""

    def __init__(
        self,
        model_name: str,
        cache_dir: Path,
        enabled: bool = True,
        batch_size: int = 32,
        allow_download: bool = False,
    ):
        self.name = model_name
        self.available = False
        self.batch_size = batch_size
        self._model = None
        if not enabled:
            logger.info("Local embeddings disabled by configuration; lexical mode active")
            return
        try:
            from fastembed import TextEmbedding

            cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(
                model_name=model_name,
                cache_dir=str(cache_dir),
                local_files_only=not allow_download,
            )
            self.available = True
            logger.info("Local embedding model loaded: %s", model_name)
        except Exception as exc:  # pragma: no cover - environment-dependent fallback
            logger.warning(
                "Local embeddings unavailable (%s). Falling back to BM25 lexical retrieval. "
                "Set EMBEDDING_ALLOW_DOWNLOAD=true on a connected first run to cache the model.",
                exc,
            )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not self.available or self._model is None:
            raise RuntimeError("Embedding backend unavailable")
        prefixed = [f"passage: {text}" for text in texts] if "e5-" in self.name.lower() else texts
        vectors = list(self._model.embed(prefixed, batch_size=self.batch_size))
        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-9, None)

    def embed_query(self, text: str) -> np.ndarray:
        if not self.available or self._model is None:
            raise RuntimeError("Embedding backend unavailable")
        prefixed = f"query: {text}" if "e5-" in self.name.lower() else text
        vector = np.asarray(list(self._model.query_embed([prefixed]))[0], dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        return vector / max(norm, 1e-9)


class VectorIndex:
    def __init__(self, chunks: list[Chunk], backend: EmbeddingBackend):
        self.chunks = chunks
        self.backend = backend
        self.matrix: np.ndarray | None = None
        if backend.available:
            try:
                self.matrix = backend.embed_documents([c.content for c in chunks])
                logger.info("Vector index built for %d chunks", len(chunks))
            except Exception as exc:  # pragma: no cover - environment-dependent fallback
                logger.warning("Vector index build failed (%s); using lexical fallback", exc)
                backend.available = False

    def search(self, query: str, limit: int = 16) -> list[tuple[Chunk, float]]:
        if not self.backend.available or self.matrix is None:
            return []
        query_vector = self.backend.embed_query(query)
        scores = self.matrix @ query_vector
        order = np.argsort(scores)[::-1][:limit]
        return [(self.chunks[int(i)], float(scores[int(i)])) for i in order]

