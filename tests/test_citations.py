from __future__ import annotations

from backend.app.guardrails.output import (
    validate_and_map_citations,
    validate_answer_claims,
)


def test_valid_citation_maps_to_actual_chunk(retriever):
    result = retriever.search("Is the 4% interest rate guaranteed?")
    text = "The 4% rate is a current assumed rate, not guaranteed. [S1]"
    validated = validate_and_map_citations(text, result.hits)
    assert validated.citations
    assert validated.citations[0].id == result.hits[0].chunk.id
    assert validated.citations[0].page == result.hits[0].chunk.page
    assert validated.citations[0].excerpt == result.hits[0].chunk.citation_excerpt
    assert "[1]" in validated.text


def test_invalid_citation_is_removed_and_flagged(retriever):
    result = retriever.search("How does withdrawal work?")
    validated = validate_and_map_citations("A claim [S99].", result.hits)
    assert validated.had_invalid
    assert validated.citations == []
    assert "S99" not in validated.text


def test_duplicate_citation_markers_share_one_source(retriever):
    result = retriever.search("How does withdrawal work?")
    validated = validate_and_map_citations("A [S1]. B [S1].", result.hits)
    assert len(validated.citations) == 1
    assert validated.text.count("[1]") == 2


def test_false_guarantee_claim_is_detected(retriever):
    result = retriever.search("Is the 4% interest rate guaranteed?")
    reason = validate_answer_claims("The 4% rate is guaranteed every year. [1]", result.hits)
    assert reason == "false_guarantee"


def test_negated_false_guarantee_is_allowed(retriever):
    result = retriever.search("Is the 4% interest rate guaranteed?")
    reason = validate_answer_claims(
        "The 4% rate is not guaranteed; it is a current assumed rate. [1]",
        result.hits,
    )
    assert reason is None


def test_unsupported_dollar_claim_is_rejected(retriever):
    result = retriever.search("How does withdrawal work?")
    reason = validate_answer_claims("You will receive $123,456. [1]", result.hits)
    assert reason and reason.startswith("unsupported_numeric_claim")

