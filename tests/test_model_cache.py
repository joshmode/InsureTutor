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


@pytest.mark.parametrize('mode', ['cached', 'missing', 'interrupted'])
def test_prepare_model_cache_reuses_or_resumes_safely(tmp_path, monkeypatch, mode):
    import sys
    import fastembed
    import huggingface_hub
    from backend.app.config import Settings
    from backend.app.scripts import download_embedding_model as command

    revision = 'a' * 40
    model_name = 'fixture/model'
    target = tmp_path / 'pinned'
    if mode == 'cached':
        target.mkdir()
        (target / 'weights.onnx').write_bytes(b'fixture')
        write_manifest(target, model_name, 'official/repo', revision)
    settings = Settings(embedding_model=model_name, embedding_local_model_dir=target, _env_file=None)
    class LocalModel:
        @staticmethod
        def list_supported_models():
            return [{'model':model_name, 'sources':{'hf':'official/repo'}, 'model_file':'weights.onnx'}]
        def __init__(self, **kwargs):
            assert kwargs['local_files_only'] is True
            assert kwargs['specific_model_path'] == str(target)
        def embed(self, texts):
            return iter([[0.0] * 384])
    downloads = []
    def download(**kwargs):
        if mode == 'cached':
            pytest.fail('A verified existing cache must not contact the model host')
        destination = Path(kwargs['local_dir'])
        assert destination.name == 'pinned.download'
        destination.mkdir(exist_ok=True)
        (destination / 'weights.onnx').write_bytes(b'fixture')
        downloads.append(destination)
        if mode == 'interrupted' and len(downloads) == 1:
            raise RuntimeError('interrupted download')
    monkeypatch.setattr(fastembed, 'TextEmbedding', LocalModel)
    monkeypatch.setattr(huggingface_hub, 'snapshot_download', download)
    monkeypatch.setattr(command, 'get_settings', lambda: settings)
    monkeypatch.setattr(sys, 'argv', ['prepare-model', '--revision', revision])
    if mode == 'interrupted':
        with pytest.raises(RuntimeError, match='interrupted download'):
            command.main()
        assert not target.exists()
    command.main()
    assert verify_manifest(target, model_name)['revision'] == revision
    assert not target.with_name('pinned.download').exists()
