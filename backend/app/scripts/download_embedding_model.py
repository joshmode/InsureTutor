from __future__ import annotations

import logging
from pathlib import Path

from fastembed import TextEmbedding

from ..config import get_settings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    settings = get_settings()
    cache = Path(settings.embedding_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    print(f"Caching {settings.embedding_model} in {cache} …")
    model = TextEmbedding(
        model_name=settings.embedding_model,
        cache_dir=str(cache),
        local_files_only=False,
    )
    vector = next(model.embed(["insurance 保險"]))
    print(f"Ready: {len(vector)}-dimension local embeddings cached.")


if __name__ == "__main__":
    main()

