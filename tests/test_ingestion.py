from __future__ import annotations

from collections import Counter
from pathlib import Path

from backend.app.ingestion.chunker import chunk_document

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "knowledge" / "FLEXI-ULife Prime Saver.pdf"


def test_chunks_are_page_aware_and_bounded():
    chunks = chunk_document(PDF)
    assert len(chunks) >= 25
    assert all(chunk.page >= 1 for chunk in chunks)
    assert all(chunk.document.endswith(".pdf") for chunk in chunks)
    assert all(chunk.id for chunk in chunks)
    assert all(len(chunk.content) <= 2200 for chunk in chunks)
    assert len({chunk.id for chunk in chunks}) == len(chunks)


def test_interest_and_withdrawal_facts_are_preserved():
    chunks = chunk_document(PDF)
    text = "\n".join(chunk.citation_excerpt for chunk in chunks)
    assert "4.0% p.a." in text
    assert "0.25% p.a." in text
    assert "2.5% p.a." in text
    assert "2.75%" in text
    assert "5.5%" in text
    assert "lapse with zero value" in text
    assert "US$25/HK$200/MOP200" in text


def test_required_page_metadata_survives_tables():
    chunks = chunk_document(PDF)
    pages = Counter(chunk.page for chunk in chunks)
    for page in (7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18):
        assert pages[page] > 0
    assert any(
        chunk.page == 10 and "Cash withdrawal" in chunk.content for chunk in chunks
    )
    assert any(
        chunk.page == 18 and "Surrender Charge" in chunk.content for chunk in chunks
    )


def test_form_rows_are_attached_to_source_values():
    chunks = chunk_document(PDF)
    minimum = next(
        chunk
        for chunk in chunks
        if chunk.page == 17 and "Minimum Sum Insured" in chunk.section
    )
    assert "US$30,000" in minimum.citation_excerpt
    assert "HK$240,000" in minimum.citation_excerpt
    payment = next(chunk for chunk in chunks if chunk.section.endswith("Payment Mode"))
    assert (
        "Annual / Semi-annual / Quarterly / Monthly Payment" in payment.citation_excerpt
    )
    currency = next(chunk for chunk in chunks if chunk.section.endswith("Currency"))
    assert "Policy issued in Hong Kong" in currency.citation_excerpt


def test_every_citation_line_exists_on_its_claimed_pdf_page():
    import re
    import pymupdf
    from backend.app.ingestion.extract import extract_pages

    normalize = lambda text: re.sub(r"[\s\x00-\x1f]+", "", text)
    with pymupdf.open(PDF) as document:
        pages = [normalize(page.get_text()) for page in document]
    # Two formula diagrams have labels in separate visual cells. The extractor
    # reconstructs their row order; retain that layout-normalized source too.
    _, layout_pages = extract_pages(PDF)
    layout = [normalize(page.text) for page in layout_pages]
    chunks = chunk_document(PDF)
    assert len(chunks) == 52
    for chunk in chunks:
        for line in chunk.citation_excerpt.splitlines():
            assert (
                normalize(line) in pages[chunk.page - 1]
                or normalize(line) in layout[chunk.page - 1]
            ), (chunk.id, line)
