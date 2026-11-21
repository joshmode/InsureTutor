from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from backend.app.config import Settings
from backend.app.ingestion.chunker import chunk_document
from backend.app.ingestion.store import KnowledgeBase


def make_pdf(path: Path, text: str, page_count=1):
    with pymupdf.open() as document:
        for _ in range(page_count):
            page = document.new_page()
            page.insert_text((40, 60), text)
        document.save(path)


def make_kb(tmp_path):
    root = tmp_path / "knowledge"
    root.mkdir()
    pdf = root / "guide.pdf"
    make_pdf(pdf, "Original coverage information for a deliberately unrelated guide.")
    settings = Settings(
        knowledge_base_dir=root,
        data_dir=tmp_path / "data",
        documents="guide.pdf",
        ingest_on_startup=False,
        _env_file=None,
    )
    return KnowledgeBase(settings), pdf


def test_source_bytes_change_invalidates_persisted_chunks(tmp_path):
    kb, pdf = make_kb(tmp_path)
    old = kb.ingest()
    pdf.unlink()
    make_pdf(pdf, "Replacement document with revised scope and conditions for testing.")
    new = kb.ensure_ready()
    assert old[0].source_sha256 != new[0].source_sha256
    assert "Replacement document" in new[0].citation_excerpt
    payload = json.loads(kb.manifest_path.read_text())
    assert payload["schema_version"] == 4
    assert payload["source_fingerprints"]["guide.pdf"] == new[0].source_sha256


def test_legacy_unfingerprinted_manifest_is_rebuilt(tmp_path):
    kb, _ = make_kb(tmp_path)
    kb.settings.data_dir.mkdir()
    kb.manifest_path.write_text("[]")
    assert kb.ensure_ready()
    assert isinstance(json.loads(kb.manifest_path.read_text()), dict)


@pytest.mark.parametrize("name", ["../outside.pdf", "/tmp/outside.pdf", "guide.txt"])
def test_unsafe_or_non_pdf_document_configuration_is_rejected(tmp_path, name):
    kb, _ = make_kb(tmp_path)
    kb.settings.documents = name
    with pytest.raises(ValueError):
        kb.ingest()


def test_symlink_outside_corpus_is_rejected(tmp_path):
    kb, pdf = make_kb(tmp_path)
    outside = tmp_path / "outside.pdf"
    pdf.rename(outside)
    pdf.symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        kb.ingest()


def test_unknown_document_does_not_receive_brochure_table_reconstruction(tmp_path):
    pdf = tmp_path / "FLEXI-ULife Prime Saver.pdf"
    make_pdf(
        pdf,
        "Plan Type\nBasic Plan\nCurrency\nPayment Mode\nExtra Bonus at a glance",
        17,
    )
    chunks = chunk_document(pdf)
    assert chunks
    assert all(c.section.startswith("Document page") for c in chunks)
    assert not any("Extra Bonus is credited" in c.citation_excerpt for c in chunks)
    assert not any("Minimum Sum Insured" in c.section for c in chunks)
    assert len(chunks) == 17
