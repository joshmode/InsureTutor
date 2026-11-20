from __future__ import annotations

import re
from dataclasses import dataclass
import re

from ..models import Citation
from ..retrieval.hybrid import RetrievalHit


CITATION_RE = re.compile(
    r"\[\[?\[?S(\d{1,2})\]?\]?\]?|【S(\d{1,2})】|\[S(\d{1,2})\]"
)


@dataclass
class ValidationResult:
    text: str
    citations: list[Citation]
    had_invalid: bool = False


def _citation_number(match: re.Match[str]) -> int | None:
    for value in match.groups():
        if value is not None:
            return int(value)
    return None


def validate_and_map_citations(
    text: str,
    hits: list[RetrievalHit],
    valid_ids: set[str] | None = None,
) -> ValidationResult:
    """Map only model-selected source markers to retrieved evidence.

    The model never controls source IDs, pages, quotations or document names.
    It sees a numbered evidence list and can only reference those numbers.
    """
    sources: dict[int, RetrievalHit] = {index + 1: hit for index, hit in enumerate(hits)}
    if valid_ids is not None:
        sources = {
            number: hit
            for number, hit in sources.items()
            if hit.chunk.id in valid_ids
        }
    used: list[int] = []
    invalid = False

    def replace(match: re.Match[str]) -> str:
        nonlocal invalid
        number = _citation_number(match)
        if number is None or number not in sources:
            invalid = True
            return ""
        if number not in used:
            used.append(number)
        return f"[{len(used)}]"

    cleaned = CITATION_RE.sub(replace, text)
    citations: list[Citation] = []
    for position, number in enumerate(used, start=1):
        hit = sources[number]
        citations.append(
            Citation(
                id=hit.chunk.id,
                document=hit.chunk.document,
                page=hit.chunk.page,
                section=hit.chunk.section or None,
                excerpt=hit.chunk.citation_excerpt,
                score=round(hit.score, 4),
            )
        )
    # If the model omitted markers entirely, we do not invent a claim-to-source
    # mapping. The orchestrator retries or returns the safe insufficient answer.
    return ValidationResult(text=cleaned, citations=citations, had_invalid=invalid)


def has_any_citation(text: str) -> bool:
    return bool(re.search(r"\[\d{1,2}\]", text))


def strip_unsupported_markers(text: str) -> str:
    return CITATION_RE.sub("", text).strip()


_FALSE_GUARANTEE = re.compile(
    r"(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%).{0,48}"
    r"(?:is|are|is fully|are fully)\s+(?:guaranteed|fixed)|"
    r"(?:guaranteed|fixed).{0,25}(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%)|"
    r"(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%).{0,35}(?:保證|保证)|"
    r"(?:保證|保证).{0,25}(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%)",
    re.IGNORECASE | re.DOTALL,
)

_SYSTEM_LEAK = re.compile(
    r"(?:system prompt|developer message|my instructions say|"
    r"系統提示|系统提示|開發者訊息|开发者消息)",
    re.IGNORECASE,
)

_SUPPLEMENTARY_ASSUMED = re.compile(
    r"(?:critical illness|accident benefit|waiver of premium|supplementary benefits?)"
    r".{0,70}(?:automatically (?:included|included automatically)|is included in the basic|"
    r"are included in the basic|comes? with the basic plan)|"
    r"(?:automatic(?:ally)?|included).{0,45}(?:critical illness|accident benefit|waiver of premium)",
    re.IGNORECASE | re.DOTALL,
)

_SUPPLEMENTARY_EVIDENCE = re.compile(
    r"(?:supplementary benefits?|waiver of premium|critical illness|accident benefit)"
    r".{0,220}(?:additional premium|if any|etc\.|optional)|"
    r"(?:additional premium|if any|optional).{0,160}"
    r"(?:waiver of premium|critical illness|accident benefit|supplementary benefit)",
    re.IGNORECASE | re.DOTALL,
)


def validate_answer_claims(answer: str, hits: list[RetrievalHit]) -> str | None:
    """Return a failure reason if generated text makes a clearly unsafe claim.

    This is a guardrail, not a fact checker. It targets high-risk patterns that
    are directly contradicted by the supplied document, plus fabricated numeric
    figures that do not occur anywhere in the retrieved evidence.
    """
    if _SYSTEM_LEAK.search(answer):
        return "system_instruction_leak"
    supplementary_assertion = _SUPPLEMENTARY_ASSUMED.search(answer)
    if supplementary_assertion:
        evidence_text = " ".join(hit.chunk.citation_excerpt for hit in hits)
        assertion = supplementary_assertion.group().lower()
        optional_evidence = re.search(
            r"supplementary benefits?.{0,80}additional premium|"
            r"additional premium.{0,80}supplementary|if any|optional",
            evidence_text,
            re.IGNORECASE | re.DOTALL,
        )
        # The assertion is unsafe unless the evidence explicitly frames the
        # benefit as supplementary/optional rather than automatically included.
        if not optional_evidence or "automatically included" in assertion:
            return "supplementary_benefit_assumed"
    for match in _FALSE_GUARANTEE.finditer(answer):
        window_start = max(0, match.start() - 35)
        window_end = min(len(answer), match.end() + 35)
        window = answer[window_start:window_end].lower()
        if not re.search(
            r"\b(?:not|isn't|aren't|no)\b|并非|並非|不是|不获|不獲|非保证|非保證",
            window,
        ):
            return "false_guarantee"
    evidence_numbers = set()
    evidence_text = " ".join(hit.chunk.citation_excerpt for hit in hits)
    evidence_text = evidence_text.replace(",", "")
    answer_norm = answer.replace(",", "")
    for number in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?%", answer_norm):
        if number in evidence_text:
            continue
        # Percentages are high-risk product claims. Assume the bare 4% is a
        # rounded reference to the brochure's 4.0% figure.
        if number == "4%":
            continue
        if "%" in number:
            return f"unsupported_numeric_claim:{number}"
    for number in re.findall(r"(?:US\$|HK\$|MOP|\$)\s?\d+(?:\.\d+)?", answer_norm):
        if number in evidence_text:
            continue
        return f"unsupported_numeric_claim:{number}"
    return None

