from __future__ import annotations

import numpy as np
import pytest

from backend.app.config import Settings
from backend.app.retrieval.embeddings import VectorIndex
from backend.app.retrieval.hybrid import HybridRetriever


@pytest.mark.parametrize("field", ["embedding_enabled", "enable_embeddings"])
def test_either_documented_switch_disables_embeddings(monkeypatch, knowledge_chunks, field):
    import backend.app.retrieval.hybrid as hybrid
    flags = []
    class DisabledBackend:
        available = False
        def __init__(self, **kwargs):
            flags.append(kwargs["enabled"])
    monkeypatch.setattr(hybrid, "LocalFastEmbedBackend", DisabledBackend)
    settings = Settings(**{field: False}, _env_file=None)
    retriever = HybridRetriever(knowledge_chunks, settings)
    assert flags == [False]
    assert retriever.mode == "lexical"


def test_query_embedding_failure_switches_to_lexical_mode(knowledge_chunks):
    class FailingBackend:
        available = True
        def embed_documents(self, texts):
            return np.ones((len(texts), 2), dtype=np.float32)
        def embed_query(self, text):
            raise RuntimeError("model execution failed")
    backend = FailingBackend()
    index = VectorIndex(knowledge_chunks, backend)
    assert index.search("interest rate") == []
    assert not backend.available
    # Once unavailable, repeated requests never retry the broken runtime.
    assert index.search("withdrawals") == []
