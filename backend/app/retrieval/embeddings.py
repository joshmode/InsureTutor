from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Protocol

import numpy as np

from ..ingestion.chunker import Chunk
from .model_cache import verify_manifest

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
        local_model_dir: Path | None = None,
    ):
        self.name = model_name
        self.available = False
        self.batch_size = batch_size
        self._model = None
        self._inference_lock = threading.Lock()
        if not enabled:
            logger.info(
                "Local embeddings disabled by configuration; lexical mode active"
            )
            return
        if allow_download:
            logger.warning(
                "Runtime downloads are disabled; cache an explicit model revision using the setup script"
            )
        try:
            local_model_dir = local_model_dir or cache_dir / "pinned"
            verify_manifest(local_model_dir, model_name)
            from fastembed import TextEmbedding
            import onnxruntime

            onnxruntime.disable_telemetry_events()
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(
                model_name=model_name,
                cache_dir=str(cache_dir),
                local_files_only=True,
                specific_model_path=str(local_model_dir),
            )
            self.available = True
            logger.info("Local embedding model loaded: %s", model_name)
        except Exception as exc:  # pragma: no cover - environment-dependent fallback
            logger.warning(
                "Local embeddings unavailable (%s). Falling back to BM25 lexical retrieval. "
                "Cache a reviewed commit using the download_embedding_model script with --revision.",
                exc,
            )

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not self.available or self._model is None:
            raise RuntimeError("Embedding backend unavailable")
        prefixed = (
            [f"passage: {text}" for text in texts]
            if "e5-" in self.name.lower()
            else texts
        )
        vectors = []
        for offset in range(0, len(prefixed), self.batch_size):
            # Share one native model safely without holding another conversation's
            # retrieval lock for an entire uploaded document.
            with self._inference_lock:
                vectors.extend(self._model.embed(
                    prefixed[offset:offset + self.batch_size], batch_size=self.batch_size
                ))
        matrix = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-9, None)

    def embed_query(self, text: str) -> np.ndarray:
        if not self.available or self._model is None:
            raise RuntimeError("Embedding backend unavailable")
        prefixed = f"query: {text}" if "e5-" in self.name.lower() else text
        with self._inference_lock:
            vector = np.asarray(
                list(self._model.query_embed([prefixed]))[0], dtype=np.float32
            )
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
            except (
                Exception
            ) as exc:  # pragma: no cover - environment-dependent fallback
                logger.warning(
                    "Vector index build failed (%s); using lexical fallback", exc
                )
                # A failed upload/index must not disable the shared model for
                # already-working conversations. This index stays lexical.

    def search(self, query: str, limit: int = 16) -> list[tuple[Chunk, float]]:
        if not self.backend.available or self.matrix is None:
            return []
        try:
            query_vector = self.backend.embed_query(query)
        except Exception as exc:
            logger.warning("Query embedding failed (%s); using lexical fallback", exc)
            self.backend.available = False
            return []
        scores = self.matrix @ query_vector
        order = np.argsort(scores)[::-1][:limit]
        return [(self.chunks[int(i)], float(scores[int(i)])) for i in order]
