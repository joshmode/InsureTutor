from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.config import Settings  # noqa: E402
from backend.app.ingestion.store import KnowledgeBase  # noqa: E402
from backend.app.retrieval.hybrid import HybridRetriever  # noqa: E402


@pytest.fixture(scope="session")
def knowledge_chunks(tmp_path_factory):
    settings = Settings(
        knowledge_base_dir=ROOT / "knowledge",
        data_dir=tmp_path_factory.mktemp("runtime"),
        embedding_enabled=False,
        enable_embeddings=False,
        ingest_on_startup=True,
        _env_file=None,
    )
    return KnowledgeBase(settings).ingest()


@pytest.fixture(scope="session")
def retriever(knowledge_chunks):
    settings = Settings(
        knowledge_base_dir=ROOT / "knowledge",
        data_dir=Path("/tmp/insuretutor-test-runtime"),
        embedding_enabled=False,
        enable_embeddings=False,
        ingest_on_startup=False,
        _env_file=None,
    )
    return HybridRetriever(knowledge_chunks, settings)

