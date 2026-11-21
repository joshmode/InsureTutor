from pathlib import Path

import pytest

from backend.app.retrieval.model_cache import verify_manifest, write_manifest


def test_model_manifest_requires_immutable_revision_and_detects_modified_files(
    tmp_path,
):
    (tmp_path / "weights.onnx").write_bytes(b"test-fixture-not-a-model")
    (tmp_path / "tokenizer.json").write_text("{}")
    with pytest.raises(ValueError):
        write_manifest(tmp_path, "model", "official/repo", "main")
    write_manifest(tmp_path, "model", "official/repo", "a" * 40)
    assert verify_manifest(tmp_path, "model")["revision"] == "a" * 40
    (tmp_path / "tokenizer.json").write_text('{"changed":true}')
    with pytest.raises(ValueError, match="integrity"):
        verify_manifest(tmp_path, "model")


def test_model_manifest_cannot_introduce_unchecked_files_or_escape_cache(tmp_path):
    directory = tmp_path / "cache"
    directory.mkdir()
    (directory / "weights.onnx").write_bytes(b"test-fixture")
    write_manifest(directory, "model", "official/repo", "b" * 40)
    (directory / "extra.json").write_text("{}")
    with pytest.raises(ValueError, match="Unmanifested"):
        verify_manifest(directory, "model")
    (directory / "extra.json").unlink()
    (tmp_path / "outside").write_bytes(b"test-fixture")
    (directory / "weights.onnx").unlink()
    (directory / "weights.onnx").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError, match="integrity"):
        verify_manifest(directory, "model")
