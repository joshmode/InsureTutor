"""Cache a local ONNX model at an explicit, reviewed Hugging Face commit.

Example: python -m backend.app.scripts.download_embedding_model --revision FULL_COMMIT
Resolve the full commit from the official model repository; never use 'main'.
No provider credentials or embeddings endpoint are involved.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from ..config import get_settings
from ..retrieval.model_cache import write_manifest, verify_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{40}", args.revision):
        parser.error("Use an exact 40-character upstream commit")
    settings = get_settings()
    # HF's transfer helper has its own cache. Keep it on the writable data
    # volume, not the container user's nonexistent/read-only home directory.
    hf_home = os.environ.setdefault(
        "HF_HOME", str(settings.embedding_cache_dir / "huggingface")
    )
    os.environ.setdefault("HF_XET_CACHE", str(Path(hf_home) / "xet"))
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from fastembed import TextEmbedding
    from huggingface_hub import snapshot_download

    description = next(
        (
            m
            for m in TextEmbedding.list_supported_models()
            if m["model"] == settings.embedding_model
        ),
        None,
    )
    if not description or not description["sources"].get("hf"):
        parser.error("This model has no supported Hugging Face source")
    repo = description["sources"]["hf"]
    target = (
        settings.embedding_local_model_dir or settings.embedding_cache_dir / "pinned"
    )
    target = Path(target)
    # Do not silently reuse a populated cache at a different revision.
    if target.exists() and any(p.name != ".cache" for p in target.iterdir()):
        try:
            existing = verify_manifest(target, settings.embedding_model)
        except (OSError, ValueError) as exc:
            raise SystemExit(
                "Use an empty EMBEDDING_LOCAL_MODEL_DIR or repair the existing manifest"
            ) from exc
        if existing["revision"] != args.revision:
            raise SystemExit("Use a separate model directory for a different revision")
    snapshot_download(
        repo_id=repo,
        revision=args.revision,
        local_dir=str(target),
        token=False,
        allow_patterns=[
            "*.json",
            "*.txt",
            "*.model",
            description["model_file"],
            *description.get("additional_files", []),
        ],
    )
    write_manifest(target, settings.embedding_model, repo, args.revision)
    verify_manifest(target, settings.embedding_model)
    model = TextEmbedding(
        model_name=settings.embedding_model,
        specific_model_path=str(target),
        local_files_only=True,
    )
    vector = next(model.embed(["insurance 保險"]))
    print(f"Verified {len(vector)}-dimension local model at revision {args.revision}")


if __name__ == "__main__":
    main()
