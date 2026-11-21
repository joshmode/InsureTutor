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
    source_sha256: str = ""

    @property
    def citation_excerpt(self) -> str:
        return self.excerpt.strip() or self.content.strip()


SECTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Flexible Protections|靈活保障"), "Flexible Protections"),
    (re.compile(r"Life Protection Options|壽險保障選擇"), "Life Protection Options"),
    (re.compile(r"Value-creating Advantages|財富增值優勢"), "Crediting & Value"),
    (
        re.compile(r"Financial Flexibilities|提存彈性"),
        "Withdrawals & Premium Flexibility",
    ),
    (
        re.compile(r"Extra Protections|額外安心保障"),
        "Additional Protections",
    ),
    (re.compile(r"Important Information|重要資料"), "Important Information"),
    (re.compile(r"Key Product Disclosures|主要產品說明"), "Key Disclosures"),
    (
        re.compile(r"Duty of Disclosure|提供資料責任"),
        "Duty of Disclosure & Cancellation",
    ),
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

FOCUS_HEADINGS = (
    "Benefits",
    "Plan Type",
    "Currency",
    "Payment Mode",
    "Minimum Sum Insured",
    "Maximum Sum Insured",
    "Increase / Decrease Sum Insured",
    "Issue Age",
    "Benefit Term",
    "Premium Payment Term",
    "Base crediting interest rate",
    "Retrospective additional interest",
    "Extra Bonus",
    "Guaranteed interest",
    "Death Benefit Options",
    "Guaranteed Insurability Option",
    "Unemployment Benefit",
    "Terminal Illness Benefit",
    "Supplementary Benefits",
    "Plan Type",
    "Currency",
    "Payment Mode",
    "Premium Expense Charge",
    "Cost of Insurance",
    "Administrative Charge",
    "Surrender Charge",
    "Cash Value Withdrawal",
    "Issue Age",
    "Benefit Term",
    "Premium Payment Term",
    "Key Exclusions",
    "Early Surrender",
    "Inflation Risk",
    "Credit Risk",
)

# The brochure's "at a glance" page is a two-column form. PyMuPDF preserves its
# visual reading order but the left-hand row label and right-hand value land in
# separate blocks. Reconstruct the known form rows with the labels that are
# printed directly beside them so a citation remains self-explanatory.
REVIEWED_BROCHURE_SHA256 = (
    "2043de40845267fdb1f657280438f3ded04edda6692791960415116a5668a475"
)

AT_A_GLANCE_ROWS: tuple[tuple[str, str], ...] = (
    ("Base crediting interest rate", "Base Crediting Interest"),
    ("Retrospective additional interest", "Retrospective additional interest"),
    ("Extra Bonus", "Extra Bonus"),
    ("Guaranteed interest", "Guaranteed interest"),
    ("Death Benefit Options", "Death Benefit Options"),
    ("Guaranteed Insurability Option", "Guaranteed Insurability Option"),
    ("Unemployment Benefit", "Unemployment Benefit"),
    ("Terminal Illness Benefit", "Terminal Illness Benefit"),
    ("Supplementary Benefits", "Supplementary Benefits"),
    ("Plan Type", "Plan Type"),
    ("Currency", "Currency"),
    ("Payment Mode", "Payment Mode"),
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
            if current and starts_new and sum(len(item) + 1 for item in current) > 180:
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
                if (
                    buffer
                    and sum(len(x) for x in buffer) + len(sentence) > target_chars
                ):
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


def _strip_form_labels(text: str) -> str:
    """Remove short standalone labels that become meaningless after packing."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    ignored = {label.lower() for label, _ in AT_A_GLANCE_ROWS} | {
        "plan type",
        "currency",
        "payment mode",
    }
    kept: list[str] = []
    for line in lines:
        if line.lower() in ignored and len(line) < 48:
            continue
        kept.append(line)
    return "\n".join(kept)


def _dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    kept: list[str] = []
    for line in text.splitlines():
        normalized = " ".join(line.split())
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        kept.append(line)
    return "\n".join(kept)


def _form_source_chunk(
    pdf_path: Path,
    page: int,
    section: str,
    lines: list[str],
    source_sha256: str,
) -> Chunk | None:
    """Create a citation chunk from actual, visually separated form cells.

    The source PDF's policy-information forms place labels and values in
    separate blocks. Concatenating those selected source lines preserves the
    relationship better than replacing them with a generated summary.
    """
    cleaned = [line.strip() for line in lines if line and line.strip()]
    if len(cleaned) < 2:
        return None
    excerpt = _chunk_excerpt("\n\n".join(cleaned))
    digest = hashlib.sha1(
        f"{pdf_path.name}:{page}:{section}:{'|'.join(cleaned)}".encode("utf-8")
    ).hexdigest()[:16]
    header = f"[{section} | {pdf_path.stem} | p.{page}]"
    return Chunk(
        id=f"{pdf_path.stem.lower().replace(' ', '-')}-p{page}-{digest}",
        document=pdf_path.name,
        page=page,
        section=section,
        content=f"{header}\n{excerpt}",
        content_type="form",
        excerpt=excerpt,
        source_sha256=source_sha256,
    )


def chunk_document(pdf_path: Path) -> list[Chunk]:
    source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    reviewed_brochure = source_sha256 == REVIEWED_BROCHURE_SHA256
    _, pages = extract_pages(pdf_path)
    chunks: list[Chunk] = []
    current_section = "Product Overview"

    for page in pages:
        if not page.text:
            continue
        page_section = (
            _section_for(page.text, current_section)
            if reviewed_brochure
            else f"Document page {page.page}"
        )
        current_section = page_section
        source_text = page.text
        if reviewed_brochure and page.page == 17:
            # This form's short Chinese value would be dropped as a standalone
            # paragraph. Keep the actual adjacent label and both source values
            # together before filtering/packing, as with the other form rows.
            label = "最高保障額\nMaximum Sum Insured"
            if label in page.blocks:
                start = page.blocks.index(label)
                row = page.blocks[start : start + 3]
                source_text = source_text.replace("\n\n".join(row), "\n".join(row))
        paragraphs = _split_paragraphs(source_text)
        pieces = _merge_short_pieces(_pack(paragraphs))
        for idx, piece in enumerate(pieces):
            section = page_section
            # Specific fee names are better retrieval anchors than a generic page
            # label. Keep the page section too in the text header.
            for heading in FEE_HEADINGS if reviewed_brochure else ():
                if heading.lower() in piece.lower():
                    section = f"{page_section} · {heading}"
                    break
            if section == page_section:
                for heading in FOCUS_HEADINGS if reviewed_brochure else ():
                    if heading.lower() in piece.lower():
                        section = f"{page_section} · {heading}"
                        break
            if reviewed_brochure and page.page == 16 and "Payment Mode" in section:
                # Preserve the Chinese payment-mode label and value from the
                # same form row, which PyMuPDF splits into separate blocks.
                mode_lines = [
                    line.strip()
                    for line in page.blocks
                    if "繳費方式" in line or "每年 / 每半年" in line
                ]
                if mode_lines:
                    piece = f"{piece}\n\n{chr(10).join(mode_lines)}"
            if reviewed_brochure and re.search(r"失業保障|Unemployment", piece, re.I):
                section = f"{page_section} · Unemployment Protection"
            if reviewed_brochure and re.search(
                r"末期病症|Terminal Illness", piece, re.I
            ):
                section = f"{page_section} · Terminal Illness"
            header = f"[{section} | {pdf_path.stem} | p.{page.page}]"
            # Page 17's minimum-sum-insured value grid is emitted before its
            # labels by PyMuPDF. Keep those verbatim rows attached to the
            # minimum-insurance passage instead of making an unlabeled chunk.
            if (
                reviewed_brochure
                and page.page == 17
                and section.endswith("Premium Expense Charge")
            ):
                value_rows = [
                    paragraph
                    for paragraph in paragraphs
                    if re.search(
                        r"us\$30,000|us\$25,000|us\$15,000|us\$8,000|us\$5,000",
                        paragraph,
                        re.I,
                    )
                ]
                if value_rows:
                    piece = f"{piece}\n\n{chr(10).join(value_rows)}"
            content = f"{header}\n{piece}"
            body = _chunk_excerpt(
                _dedupe_lines(_strip_form_labels(piece) if reviewed_brochure else piece)
            )
            digest = hashlib.sha1(
                f"{pdf_path.name}:{page.page}:{idx}:{piece}".encode("utf-8")
            ).hexdigest()[:16]
            chunks.append(
                Chunk(
                    id=f"{pdf_path.stem.lower().replace(' ', '-')}-p{page.page}-{digest}",
                    document=pdf_path.name,
                    page=page.page,
                    section=section,
                    content=content,
                    content_type="table" if _table_like(piece) else "prose",
                    excerpt=body.strip(),
                    source_sha256=source_sha256,
                )
            )
    # Reconstruct two source form sections from their actual PDF labels/values.
    for page in pages if reviewed_brochure else ():
        if page.page == 17:
            labels = [
                line
                for line in page.blocks
                if line.strip()
                in {
                    "Minimum Sum Insured",
                    "Maximum Sum Insured",
                    "Increase / Decrease Sum Insured",
                }
            ]
            values = [
                line
                for line in page.blocks
                if re.match(
                    r"^(?:< Age 45|≥ Age 45|FP80/100/130|FP180/280|其他 Others|"
                    r"香港保單|澳門保單|US\$|HK\$|MOP)",
                    line.strip(),
                )
            ]
            if values:
                excerpt_lines = ["Minimum Sum Insured", *values]
                form_chunk = _form_source_chunk(
                    pdf_path,
                    17,
                    "Life Protection Options · Minimum Sum Insured",
                    excerpt_lines,
                    source_sha256,
                )
                if form_chunk:
                    chunks.append(form_chunk)
        if page.page == 18:
            # These form labels are immediately followed by their own Chinese
            # and English values in the reviewed PDF text layer. Preserve each
            # row separately; paragraph packing otherwise separates To Age 100
            # from its label (or attaches the label to a surrender-charge row).
            for label, section in (
                (
                    "投保年齡（以上次生日年齡計算）\nIssue Age (At Last Birthday)",
                    "Issue Age",
                ),
                ("保障年期\nBenefit Term", "Benefit Term"),
                ("繳付保費年期\nPremium Payment Term", "Premium Payment Term"),
            ):
                if label in page.blocks:
                    start = page.blocks.index(label)
                    form_chunk = _form_source_chunk(
                        pdf_path,
                        18,
                        f"Basic Information · {section}",
                        list(page.blocks[start : start + 3]),
                        source_sha256,
                    )
                    if form_chunk:
                        chunks.append(form_chunk)
        if page.page == 16:
            required = {
                "Plan Type": ["保單類別\nPlan Type", "基本計劃"],
                "Currency": [
                    "保單貨幣單位\nCurrency",
                    "香港保單",
                    "澳門保單",
                    "Policy issued in Hong Kong",
                ],
                "Payment Mode": [
                    "繳費方式\nPayment Mode",
                    "每年 / 每半年",
                    "Annual / Semi-annual / Quarterly / Monthly Payment",
                ],
            }
            for section_name, needles in required.items():
                selected = [
                    line
                    for line in page.blocks
                    if any(needle in line for needle in needles)
                ]
                if selected:
                    form_chunk = _form_source_chunk(
                        pdf_path,
                        16,
                        f"Plan at a Glance · {section_name}",
                        selected,
                        source_sha256,
                    )
                    if form_chunk:
                        chunks.append(form_chunk)
    return chunks
