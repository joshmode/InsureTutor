"""Bounded child process for parsing an untrusted PDF; no provider credentials."""
from __future__ import annotations

import json
import resource
import sys
from dataclasses import asdict
from pathlib import Path


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1024 * 1024,) * 2)
    import pymupdf
    from .chunker import chunk_document

    source, output = map(Path, sys.argv[1:])
    with pymupdf.open(source) as document:
        if not document.is_pdf or document.needs_pass or document.is_encrypted:
            raise ValueError("A readable, unencrypted PDF is required")
        pages = len(document)
        if not 1 <= pages <= 100:
            raise ValueError("PDF must have 1–100 pages")
    chunks = chunk_document(source)
    if not chunks or len(chunks) > 1000:
        raise ValueError("PDF must contain extractable text")
    if sum(len(c.content) for c in chunks) > 2 * 1024 * 1024:
        raise ValueError("Too much extracted text")
    output.write_text(json.dumps({"pages": pages, "chunks": [asdict(c) for c in chunks]}))


if __name__ == "__main__":
    main()
