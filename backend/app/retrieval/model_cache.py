"""Integrity metadata for a model downloaded at an explicit upstream commit.

The manifest detects stale/changed cache contents, not a malicious local
administrator who can rewrite both the files and manifest. Trust originates in
an operator-selected full upstream revision and HTTPS artifact acquisition.
"""

import hashlib
import json
import re
from pathlib import Path

MANIFEST = "insuretutor-model.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(directory: Path, model: str, repository: str, revision: str):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("An exact 40-character upstream model commit is required")
    files = {
        str(p.relative_to(directory)): sha256(p)
        for p in directory.rglob("*")
        if p.is_file()
        and ".cache" not in p.relative_to(directory).parts
        and p.name != MANIFEST
    }
    if not files or not any(name.endswith(".onnx") for name in files):
        raise ValueError("The pinned model must contain ONNX weights")
    (directory / MANIFEST).write_text(
        json.dumps(
            {
                "model": model,
                "repository": repository,
                "revision": revision,
                "files": files,
            },
            indent=2,
        )
        + "\n"
    )


def verify_manifest(directory: Path, model: str) -> dict:
    directory = directory.resolve()
    manifest = json.loads((directory / MANIFEST).read_text())
    if manifest.get("model") != model or not re.fullmatch(
        r"[0-9a-f]{40}", str(manifest.get("revision", ""))
    ):
        raise ValueError("Pinned model identity/revision mismatch")
    files = manifest.get("files")
    if (
        not isinstance(files, dict)
        or not files
        or not any(name.endswith(".onnx") for name in files)
    ):
        raise ValueError("Pinned model file manifest is incomplete")
    for name, digest in files.items():
        candidate = (directory / name).resolve()
        if (
            not candidate.is_relative_to(directory)
            or not candidate.is_file()
            or sha256(candidate) != digest
        ):
            raise ValueError("Pinned model integrity validation failed")
    # Unmanifested model files could otherwise override an approved tokenizer.
    actual = {
        str(p.relative_to(directory))
        for p in directory.rglob("*")
        if p.is_file()
        and ".cache" not in p.relative_to(directory).parts
        and p.name != MANIFEST
    }
    if actual != set(files):
        raise ValueError("Unmanifested model artifacts found")
    return manifest
