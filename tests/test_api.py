from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import get_settings
from backend.app.main import app


def test_health_and_static_frontend(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(Path("knowledge").resolve()))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EMBEDDING_ENABLED", "false")
    monkeypatch.setenv("ENABLE_EMBEDDINGS", "false")
    monkeypatch.setenv("CHAT_TIMEOUT_SECONDS", "271")
    monkeypatch.setenv("REQUEST_READ_TIMEOUT_SECONDS", "9")
    get_settings.cache_clear()
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["chunks"] > 0
        assert health.json()["request_timeout_seconds"] == 285
        page = client.get("/")
        assert page.status_code == 200


def test_empty_messages_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(Path("knowledge").resolve()))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_EMBEDDINGS", "false")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={"message": "   ", "language": "en"},
        )
        assert response.status_code == 422


def test_chat_api_returns_source_excerpts_without_llm_key(tmp_path, monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_DIR", str(Path("knowledge").resolve()))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENABLE_EMBEDDINGS", "false")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "What happens if I keep withdrawing money?",
                "language": "en",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["citations"]
        assert all(citation["page"] >= 1 for citation in body["citations"])


def test_no_secret_value_checked_into_example():
    text = Path(".env.example").read_text()
    assert "LLM_API_KEY=\n" in text


def test_frontend_cannot_serve_files_outside_export(tmp_path, monkeypatch):
    from backend.app import main
    export = tmp_path / "out"
    export.mkdir()
    (export / "index.html").write_text("<html>UI</html>")
    (tmp_path / "secret.txt").write_text("private-setting")
    (export / "escaped.txt").symlink_to(tmp_path / "secret.txt")
    monkeypatch.setattr(main, "STATIC_DIR", export)
    with TestClient(app) as client:
        for path in ["/%2e%2e/secret.txt", "/escaped.txt"]:
            response = client.get(path)
            assert response.status_code == 404
            assert "private-setting" not in response.text
        assert client.get("/").status_code == 200
        assert client.get("/api/missing").status_code == 404


def test_source_document_selects_only_configured_pdfs_in_knowledge_root(
    tmp_path, monkeypatch
):
    import pymupdf

    from backend.app import main
    from backend.app.config import Settings

    corpus = tmp_path / "knowledge"
    corpus.mkdir()
    for filename, text in [("First plan.pdf", "First plan"), ("第二份計劃.pdf", "Second plan")]:
        with pymupdf.open() as pdf:
            pdf.new_page().insert_text((72, 72), text)
            pdf.save(corpus / filename)
    outside = tmp_path / "Outside.pdf"
    outside.write_bytes((corpus / "First plan.pdf").read_bytes())
    (corpus / "Escaped.pdf").symlink_to(outside)
    monkeypatch.setattr(
        main,
        "settings",
        Settings(
            knowledge_base_dir=corpus,
            documents="First plan.pdf,第二份計劃.pdf,Escaped.pdf,Missing.pdf",
            _env_file=None,
        ),
    )

    # No application startup is needed to verify this file-serving boundary.
    client = TestClient(app)
    first = client.get("/source-document")
    second = client.get("/source-document", params={"document": "第二份計劃.pdf"})
    assert first.status_code == second.status_code == 200
    assert second.headers["content-type"] == "application/pdf"
    assert first.content == (corpus / "First plan.pdf").read_bytes()
    assert second.content == (corpus / "第二份計劃.pdf").read_bytes()
    assert first.content != second.content
    for name in ["Other.pdf", "../Outside.pdf", str(outside), "Escaped.pdf", "Missing.pdf"]:
        assert client.get("/source-document", params={"document": name}).status_code == 404

