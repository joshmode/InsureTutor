from __future__ import annotations

import pytest

from backend.app.config import Settings
from backend.app.retrieval.hybrid import HybridRetriever


@pytest.mark.parametrize("question", ["冷靜期有多長？", "冷静期有多长？", "What is the benefit term?"])
def test_strong_literal_source_survives_a_missing_vector_candidate(knowledge_chunks, monkeypatch, question):
    retriever = HybridRetriever(knowledge_chunks, Settings(enable_embeddings=False, _env_file=None))
    retriever.embedding_backend.available = True
    # Simulate an existing vector index whose candidate search returns nothing.
    import numpy as np
    retriever.vector.matrix = np.ones((len(knowledge_chunks), 2), dtype=np.float32)
    monkeypatch.setattr(retriever.vector, "search", lambda query, limit: [])
    result = retriever.search(question)
    assert result.mode == "hybrid"
    assert result.sufficient and result.hits
    assert result.hits[0].lexical_score >= 0.8


def pages(result):
    return {hit.chunk.page for hit in result.hits}


def test_interest_question_retrieves_interest_pages(retriever):
    result = retriever.search("Is the 4% interest rate guaranteed?")
    assert result.sufficient
    assert result.hits
    assert pages(result) & {8, 13, 16}
    assert any(
        "4.0% p.a." in hit.chunk.content or "4%" in hit.chunk.content
        for hit in result.hits
    )
    assert all(hit.chunk.id and hit.chunk.document and hit.chunk.page for hit in result.hits)


def test_withdrawal_question_retrieves_withdrawal_and_lapse(retriever):
    result = retriever.search(
        "What happens if I keep withdrawing money from the policy?"
    )
    assert result.sufficient
    combined = " ".join(hit.chunk.content for hit in result.hits)
    assert "Cash withdrawal" in combined
    assert ("lapse" in combined.lower()) or ("terminated" in combined.lower())
    assert pages(result) & {10, 14, 18}


def test_simplified_chinese_question_retrieves_english_content(retriever):
    result = retriever.search(
        "这个保险的4%利息是保证的吗？如果不是，什么是2.5%的保证利率？"
    )
    assert result.sufficient
    assert pages(result) & {8, 13, 16}
    assert any("2.5% p.a." in hit.chunk.content for hit in result.hits)


def test_traditional_chinese_question_retrieves_relevant_content(retriever):
    result = retriever.search("如果我暫停繳付保費，會有什麼影響？")
    assert result.sufficient
    assert any(
        "Skip Premium Payments" in hit.chunk.content
        or "暫停繳付保費" in hit.chunk.content
        for hit in result.hits
    )


def test_comparison_retrieves_life_protection_page(retriever):
    result = retriever.search(
        "What is the difference between Level Benefit and Increasing Benefit?"
    )
    assert result.sufficient
    assert 7 in pages(result)


def test_unrelated_question_is_low_confidence(retriever):
    result = retriever.search("What is the capital of France?")
    assert not result.sufficient


def test_low_k_does_not_pad_irrelevant_results(retriever):
    result = retriever.search("Tell me about quantum chromodynamics", top_k=8)
    assert not result.sufficient
    assert not result.hits or all(hit.score >= retriever.settings.min_relevance_score for hit in result.hits)


def test_minimum_sum_retrieves_policy_limits_page(retriever):
    result = retriever.search("What is the minimum sum insured?")
    assert result.sufficient
    assert 17 in pages(result)
    assert any(
        "US$30,000" in hit.chunk.citation_excerpt
        for hit in result.hits
        if hit.chunk.page == 17
    )


def test_payment_mode_retrieves_at_a_glance(retriever):
    result = retriever.search("What payment modes are available?")
    assert result.sufficient
    assert 16 in pages(result)
    assert any(
        "Annual / Semi-annual / Quarterly / Monthly" in hit.chunk.citation_excerpt
        or "法定" in hit.chunk.citation_excerpt
        for hit in result.hits
    )



def test_printed_exclusion_heading_survives_missing_vector_candidate(retriever, monkeypatch):
    monkeypatch.setattr(retriever.embedding_backend, 'available', True)
    monkeypatch.setattr(retriever.vector, 'search', lambda *args, **kwargs: [])
    result = retriever.search('What are the exclusions?')
    assert result.sufficient
    assert any('exclusions' in h.chunk.citation_excerpt.lower() for h in result.hits)
