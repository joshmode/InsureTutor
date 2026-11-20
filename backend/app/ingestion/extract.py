from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    width: float
    height: float
    blocks: tuple[str, ...] = ()


@dataclass(frozen=True)
class TextLine:
    x: float
    y: float
    text: str


def _clean_text(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\x00", "")
    text = text.replace("\ufffe", "")
    text = text.replace("\x07", "")
    text = re.sub(r"[\u200b\u200c\u200d\u2060]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_page_furniture(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return bool(re.fullmatch(r"(?:page)?\d{1,3}", compact, re.I))


def _render_block(block: dict) -> str:
    """Keep separate visual columns on separate lines.

    PyMuPDF groups tightly-spaced table cells into one block. Joining all spans
    loses the boundary between "policy year 1", "4%" and "0.25%"; preserving
    lines lets the chunk retain a legible row structure.
    """
    lines: list[TextLine] = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        text = "".join(str(span.get("text", "")) for span in spans).strip()
        if not text:
            continue
        bbox = line.get("bbox", (0, 0, 0, 0))
        lines.append(TextLine(x=float(bbox[0]), y=float(bbox[1]), text=text))
    if not lines:
        return ""
    # Multiple cells sharing the same baseline are rendered with separators.
    rows: dict[int, list[TextLine]] = {}
    for line in lines:
        bucket = round(line.y / 3)
        rows.setdefault(bucket, []).append(line)
    rendered: list[str] = []
    for row in rows.values():
        row.sort(key=lambda item: item.x)
        rendered.append("  ".join(item.text for item in row))
    return _clean_text("\n".join(rendered))


def extract_pages(pdf_path: Path) -> tuple[dict[str, str], list[PageText]]:
    """Extract text and document metadata without losing page identity."""
    document = pymupdf.open(pdf_path)
    try:
        metadata = {str(k): str(v) for k, v in (document.metadata or {}).items() if v}
        pages: list[PageText] = []
        for index, page in enumerate(document):
            blocks = []
            for block in page.get_text("dict", sort=False).get("blocks", []):
                if block.get("type") != 0:
                    continue
                block_text = _render_block(block)
                if not block_text or _is_page_furniture(block_text):
                    continue
                blocks.append(block_text)
            # Reading order from the PDF text layer is preferable to geometric
            # sorting for this bilingual two-column brochure: sorted output
            # interleaves both languages and destroys table rows.
            text = "\n\n".join(blocks)
            text = "\n\n".join(blocks)
            pages.append(
                PageText(
                    page=index + 1,
                    text=text,
                    width=float(page.rect.width),
                    height=float(page.rect.height),
                    blocks=tuple(blocks),
                )
            )
        return metadata, pages
    finally:
        document.close()
