from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .extract import PageText, extract_pages


@dataclass(frozen=True)
class Chunk:
    id: str
    document: str
    page: int
    section: str
    content: str
    content_type: str = "prose"
    excerpt: str = ""

    @property
    def citation_excerpt(self) -> str:
        return self.excerpt.strip() or self.content.strip()


SECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Flexible Protections|靈活保障"), "Flexible Protections"),
    (re.compile(r"Life Protection Options|壽險保障選擇"), "Life Protection Options"),
    (re.compile(r"Value-creating Advantages|財富增值優勢"), "Crediting & Value"),
    (re.compile(r"Financial Flexibilities|提存彈性"), "Withdrawals & Premium Flexibility"),
    (
        re.compile(r"Extra Protections|額外安心保障"),
        "Additional Protections",
    ),
    (re.compile(r"Important Information|重要資料"), "Important Information"),
    (re.compile(r"Key Product Disclosures|主要產品說明"), "Key Disclosures"),
    (re.compile(r"Duty of Disclosure|提供資料責任"), "Duty of Disclosure & Cancellation"),
    (re.compile(r"at a glance|一覽表"), "Plan at a Glance"),
    (re.compile(r"Policy Information|保單資料"), "Policy Information"),
)

FEE_HEADINGS = (
    "Premium Expense Charge",
    "Cost of Insurance",
    "Administrative Charge",
    "Surrender Charge",
    "Cash Value Withdrawal",
)


def _section_for(page_text: str, fallback: str) -> str:
    head = page_text[:2400]
    for pattern, name in SECTION_PATTERNS:
        if pattern.search(head):
            return name
    return fallback


def _split_paragraphs(text: str) -> list[str]:
    # PDF extraction places bilingual paragraphs in visual reading order. Blank
    # lines are reliable boundaries; numbered clauses and bullet rows are also
    # kept intact where possible.
    blocks = re.split(r"\n\s*\n", text)
    paragraphs: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        current: list[str] = []
        for line in lines:
            starts_new = bool(
                re.match(r"^(?:\d{1,2}[.)]|[-•■▪]|[A-Z][A-Za-z /-]{2,}:)", line)
                or re.match(r"^(?:[A-Z][a-z]+ ){1,3}[A-Z][a-z]+$", line)
            )
            if (
                current
                and starts_new
                and sum(len(item) + 1 for item in current) > 180
            ):
                paragraphs.append(" ".join(current).strip())
                current = [line]
            else:
                current.append(line)
        if current:
            paragraphs.append(" ".join(current).strip())
    return [p for p in paragraphs if len(p) >= 24]


def _pack(paragraphs: list[str], target_chars: int = 950) -> list[str]:
    """Pack paragraphs to a bounded size without cutting a paragraph."""
    packed: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if paragraph_len > target_chars * 1.65:
            if current:
                packed.append("\n\n".join(current))
                current, current_len = [], 0
            # Very long bilingual tables are split at sentence boundaries, not
            # in the middle of a word. Context is restored in the section title.
            sentences = re.split(r"(?<=[。；;.!?])\s+|\n+", paragraph)
            buffer: list[str] = []
            for sentence in sentences:
                if not sentence.strip():
                    continue
                if buffer and sum(len(x) for x in buffer) + len(sentence) > target_chars:
                    packed.append(" ".join(buffer))
                    buffer = []
                buffer.append(sentence.strip())
            if buffer:
                packed.append(" ".join(buffer))
            continue
        if current and current_len + paragraph_len > target_chars:
            packed.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(paragraph)
        current_len += paragraph_len + 2
    if current:
        packed.append("\n\n".join(current))
    return packed


def _merge_short_pieces(pieces: list[str], minimum_chars: int = 280) -> list[str]:
    """Keep related table labels and captions with their surrounding content."""
    merged: list[str] = []
    pending = ""
    for piece in pieces:
        if pending:
            piece = f"{pending}\n\n{piece}"
            pending = ""
        if len(piece) < minimum_chars:
            pending = piece
            continue
        merged.append(piece)
    if pending:
        if merged and len(pending) < minimum_chars:
            merged[-1] = f"{merged[-1]}\n\n{pending}"
        else:
            merged.append(pending)
    return merged


def _table_like(text: str) -> bool:
    if text.count("\n") >= 4 and re.search(r"\$|\d+%|US\$|HK\$|MOP", text):
        return True
    return bool(re.search(r"(?m)^(?:\d{1,2})\s+\d+(?:\.\d+)?%\s+\d", text))


def _chunk_excerpt(piece: str) -> str:
    """Keep citations readable and avoid a maximal mobile source panel."""
    text = re.sub(r"\x07", " ", piece)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_document(pdf_path: Path) -> list[Chunk]:
    metadata, pages = extract_pages(pdf_path)
    doc_title = metadata.get("title") or pdf_path.stem
    chunks: list[Chunk] = []
    current_section = "Product Overview"

    for page in pages:
        if not page.text:
            continue
        page_section = _section_for(page.text, current_section)
        current_section = page_section
        paragraphs = _split_paragraphs(page.text)
        pieces = _merge_short_pieces(_pack(paragraphs))
        for idx, piece in enumerate(pieces):
            section = page_section
            # Specific fee names are better retrieval anchors than a generic page
            # label. Keep the page section too in the text header.
            for heading in FEE_HEADINGS:
                if heading.lower() in piece.lower():
                    section = f"{page_section} · {heading}"
                    break
            if re.search(r"失業保障|Unemployment", piece, re.I):
                section = f"{page_section} · Unemployment Protection"
            if re.search(r"末期病症|Terminal Illness", piece, re.I):
                section = f"{page_section} · Terminal Illness"
            header = f"[{section} | {pdf_path.stem} | p.{page.page}]"
            content = f"{header}\n{piece}"
            body = _chunk_excerpt(re.sub(r"^\[[^\n]*\n", "", content))
            digest = hashlib.sha1(
                f"{pdf_path.name}:{page.page}:{idx}:{piece}".encode("utf-8")
            ).hexdigest()[:16]
            chunks.append(
                Chunk(
                    id=f"{pdf_path.stem.lower().replace(' ', '-')}-p{page.page}-{digest}",
                    document=doc_title if doc_title.endswith(".pdf") else pdf_path.name,
                    page=page.page,
                    section=section,
                    content=content,
                    content_type="table" if _table_like(piece) else "prose",
                    excerpt=body.strip(),
                )
            )
    return chunks

