from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ..models import Citation
from ..retrieval.hybrid import RetrievalHit


CITATION_RE = re.compile(r"\[+S(\d+)\]+|【S(\d+)】")


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
        return f"[{used.index(number) + 1}]"

    # Bare display numbers are not evidence identifiers. Accepting one valid
    # marker must not let a hallucinated [99] survive beside it.
    invalid = bool(re.search(r"\[\d+\]", text))
    cleaned = re.sub(r"\[\d+\]", "", text)
    cleaned = CITATION_RE.sub(replace, cleaned)
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
    r"(?:is|are|is fully|are fully)\s+(?:guaranteed|guarantees?|fixed)|"
    r"(?:guaranteed|guarantees?|fixed).{0,25}(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%)|"
    r"(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%).{0,35}(?:保證|保证)|"
    r"(?:保證|保证).{0,25}(?:4(?:\.0)?%|0\.25%|2\.75%|5\.5%)",
    re.IGNORECASE | re.DOTALL,
)

_ANNUAL_GUARANTEE = re.compile(
    r"2\.5\s*[%％].{0,25}(?:guaranteed|guarantees?|fixed).{0,25}(?:every|each|annually)|"
    r"(?:guaranteed|guarantees?|fixed).{0,25}2\.5\s*[%％].{0,25}(?:every|each|annually)|"
    r"(?:每年|每一年).{0,15}(?:保證|保证).{0,15}2\.5\s*[%％]|"
    r"2\.5\s*[%％].{0,15}(?:每年|每一年).{0,15}(?:保證|保证)",
    re.IGNORECASE,
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

_PERSONAL_RECOMMENDATION = re.compile(
    r"\b(?:you should|you must|i recommend(?: that you)?)\s+(?:not\s+)?"
    r"(?:buy(?:ing)?|purchas(?:e|ing)|invest(?:ing)?|surrender(?:ing)?|cancel(?:ling)?|keep(?:ing)?|switch(?:ing)?)|"
    r"\b(?:this (?:policy|plan)|it) is (?:definitely |very |perfectly )?"
    r"(?:suitable|ideal|perfect|right) for you|"
    r"(?:你|您)(?:應該|应该|必須|必须)(?:購買|购买|買|买|退保|投資|投资)|"
    r"(?:此|這|这)(?:份|個|个)?(?:保單|保单|計劃|计划).{0,8}(?:適合|适合)(?:你|您)",
    re.IGNORECASE,
)


def _numbers(text: str) -> set[tuple[str, Decimal]]:
    """Compare complete amounts, not substrings (5% is not 2.5%)."""
    text = text.replace(",", "")
    numbers = {
        ("%", Decimal(value))
        for value in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[%％]", text)
    }
    numbers.update(
        (currency.upper(), Decimal(value))
        for currency, value in re.findall(
            r"(US\$|HK\$|MOP|\$)\s*(\d+(?:\.\d+)?)", text, re.I
        )
    )
    return numbers


def validate_answer_claims(answer: str, hits: list[RetrievalHit]) -> str | None:
    """Return a failure reason if generated text makes a clearly unsafe claim.

    This is a guardrail, not a fact checker. It targets high-risk patterns that
    are directly contradicted by the supplied document, plus fabricated numeric
    figures that do not occur anywhere in the retrieved evidence.
    """
    if _SYSTEM_LEAK.search(answer):
        return "system_instruction_leak"
    if _PERSONAL_RECOMMENDATION.search(answer):
        return "personalized_recommendation"
    supplementary_assertion = _SUPPLEMENTARY_ASSUMED.search(answer)
    if supplementary_assertion:
        # Optional coverage in the evidence does not support asserting that it
        # comes with the basic plan. Permit an explicit local negation only.
        if not re.search(r"\b(?:not|never|isn't|aren't)\b", supplementary_assertion.group(), re.I):
            return "supplementary_benefit_assumed"
    # Check separate sentences so an unrelated disclaimer cannot negate a
    # contradictory promise in the preceding sentence.
    clauses = re.split(r"(?<=[.!?。；;])\s+|\n", answer)
    for clause in clauses:
        for match in (*_FALSE_GUARANTEE.finditer(clause), *_ANNUAL_GUARANTEE.finditer(clause)):
            window = clause[max(0, match.start() - 15):match.end()].lower()
            if not re.search(
                r"\b(?:not|isn't|aren't|never|no)\s+(?:(?:a|an|fully|fixed)\s+){0,2}"
                r"(?:guaranteed|guarantee|fixed)|"
                r"(?:并非|並非|不是|不获|不獲|非)\s*(?:保證|保证|固定)",
                window,
            ):
                return "false_guarantee"
    evidence_text = " ".join(hit.chunk.citation_excerpt for hit in hits)
    plain_answer = answer.replace("*", "").replace("_", "")
    # The brochure restarts this period for increased cover. A bare "first
    # 14 years" summary can imply the charge disappears at policy year 14.
    # Apply this narrow gate only when the claim's own source states the restart.
    if (
        re.search(r"surrender charges?|退保[費费]用", plain_answer, re.I)
        and re.search(r"(?:14|十四)\s*[- ]*(?:policy\s+)?(?:years?|年)", plain_answer, re.I)
        and re.search(
            r"effective date of each increase|每次增加基本保障[額额]的生效日期",
            " ".join(evidence_text.split()), re.I,
        )
    ):
        original_start = re.search(
            r"policy\s+(?:date|inception|start|issue date)|保[單单](?:日期|生效日)|(?:each|per)\s+layer|每[層层]",
            plain_answer, re.I,
        )
        increased_cover = re.search(
            r"(?:each|every|any)\s+(?:increase|new\s+layer)|(?:each|per)\s+layer|每次增加|每[層层]",
            plain_answer, re.I,
        )
        if not original_start or not increased_cover:
            return "missing_surrender_charge_start_events"
    unsupported = _numbers(answer) - _numbers(evidence_text)
    if unsupported:
        return "unsupported_numeric_claim"
    return None

