from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from backend.app.config import Settings
from backend.app.retrieval.embeddings import VectorIndex
from backend.app.retrieval.hybrid import HybridRetriever


def test_shared_model_inference_is_serialized_and_documents_are_bounded():
    import concurrent.futures
    import threading
    import time
    from backend.app.retrieval.embeddings import LocalFastEmbedBackend
    active = 0
    calls = []
    lock = threading.Lock()
    class Model:
        def embed(self, texts, **kwargs):
            nonlocal active
            with lock:
                active += 1
                assert active == 1
                calls.append(len(texts))
                assert len(texts) <= 2
            try:
                time.sleep(.01)
                yield from ([1., 0.] for _ in texts)
            finally:
                with lock:
                    active -= 1
        def query_embed(self, texts):
            return self.embed(texts)
    backend = LocalFastEmbedBackend('test', Path('/tmp'), enabled=False, batch_size=2)
    backend._model, backend.available = Model(), True
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        documents = pool.submit(backend.embed_documents, ['a'] * 5)
        query = pool.submit(backend.embed_query, 'a')
        assert documents.result().shape == (5, 2)
        assert query.result().shape == (2,)
    assert sorted(calls) == [1, 1, 2, 2]


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


def test_one_document_index_failure_does_not_disable_other_conversations(knowledge_chunks):
    class Backend:
        available = True
        def embed_documents(self, texts):
            if texts == ['bad document']:
                raise RuntimeError('This document could not be embedded')
            return np.ones((len(texts), 2), dtype=np.float32)
        def embed_query(self, text):
            return np.ones(2, dtype=np.float32)
    from backend.app.ingestion.chunker import Chunk
    backend = Backend()
    default = VectorIndex(knowledge_chunks, backend)
    failed = VectorIndex([Chunk('bad', 'bad.pdf', 1, '', 'bad document')], backend)
    assert failed.search('test') == []
    assert backend.available
    assert default.search('test')
