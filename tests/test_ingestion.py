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
    assert any(chunk.page == 18 and "Surrender Charge" in chunk.content for chunk in chunks)

