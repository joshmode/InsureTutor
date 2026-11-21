from __future__ import annotations

from backend.app.guardrails.output import (
    validate_and_map_citations,
    validate_answer_claims,
)
import pytest
from backend.app.ingestion.chunker import Chunk
from backend.app.retrieval.hybrid import RetrievalHit


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


def test_repeated_citations_keep_original_number_after_another_source(retriever):
    result = retriever.search("How does withdrawal work?")
    validated = validate_and_map_citations("A [S2]. B [S1]. C [S2].", result.hits)
    assert validated.text == "A [1]. B [2]. C [1]."
    assert [c.id for c in validated.citations] == [result.hits[1].chunk.id, result.hits[0].chunk.id]


@pytest.mark.parametrize("marker", ["[99]", "[S100]", "[S0]"])
def test_mixed_real_and_fabricated_markers_are_rejected(retriever, marker):
    result = retriever.search("How does withdrawal work?")
    validated = validate_and_map_citations(f"A [S1]. B {marker}.", result.hits)
    assert validated.had_invalid
    assert marker not in validated.text


@pytest.mark.parametrize("answer", ["The rate is 5%.", "The charge is US$400.", "The rate is 4%."])
def test_numeric_claim_requires_complete_matching_value(answer):
    hits = [RetrievalHit(Chunk("id", "test.pdf", 1, "test", "2.5% and US$400,000"), 1, 1, 0)]
    assert validate_answer_claims(answer, hits) == "unsupported_numeric_claim"


def test_equivalent_decimal_percentage_is_supported():
    hits = [RetrievalHit(Chunk("id", "test.pdf", 1, "test", "4.0% and US$4"), 1, 1, 0)]
    assert validate_answer_claims("The assumed rate is 4% and the charge is US$4.", hits) is None


def test_unrelated_disclaimer_does_not_excuse_false_guarantee():
    assert validate_answer_claims("Not financial advice: 4% is guaranteed every year.", []) == "false_guarantee"
    assert validate_answer_claims("The policy guarantees a 4% return.", []) == "false_guarantee"
    assert validate_answer_claims("The 4% rate is guaranteed. It is not guaranteed at 10%.", []) == "false_guarantee"


@pytest.mark.parametrize("answer", [
    "2.5% is guaranteed every year. [1]",
    "You get a guaranteed 2.5% each year. [1]",
    "每年保证获得2.5%。 [1]",
])
def test_long_term_floor_is_not_an_annual_guarantee(answer):
    assert validate_answer_claims(answer, []) == "false_guarantee"


@pytest.mark.parametrize("answer", [
    "You should buy this policy. [1]",
    "I recommend buying this policy. [1]",
    "This plan is suitable for you. [1]",
    "您应该购买此保险。 [1]",
])
def test_personal_recommendation_is_rejected(answer):
    assert validate_answer_claims(answer, []) == "personalized_recommendation"


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


def test_citation_markers_in_markdown_are_mapped(retriever):
    result = retriever.search("Is the 4% interest rate guaranteed?")
    validated = validate_and_map_citations(
        "- The 4.0% rate is an assumed rate. [S1]\n- The guarantee has conditions. [S2]",
        result.hits,
    )
    assert len(validated.citations) == 2
    assert validated.text.count("[1]") == 1
    assert validated.text.count("[2]") == 1

