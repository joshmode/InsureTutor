"""Reviewed conflict in the exact supplied brochure, never generalized to others."""

from __future__ import annotations

import re

from ..ingestion.chunker import REVIEWED_BROCHURE_SHA256
from ..models import ChatResponse
from ..retrieval.hybrid import RetrievalHit
from .output import validate_and_map_citations
from .policy import localised_notice


def source_conflict_response(
    question: str, language: str, hits: list[RetrievalHit]
) -> ChatResponse | None:
    if not re.search(
        r"increase|decrease|增加|減少|减少|加保|減保|减保", question, re.I
    ):
        return None
    if not re.search(
        r"sum insured|cover(?:age)?|保障額|保障额|保額|保额", question, re.I
    ):
        return None
    if not re.search(r"amount|minimum|how much|金額|金额|最低|多少", question, re.I):
        return None
    relevant = [
        h
        for h in hits
        if h.chunk.source_sha256 == REVIEWED_BROCHURE_SHA256
        and h.chunk.page == 17
        and "minimum amount of increase / decrease" in h.chunk.citation_excerpt.lower()
    ]
    if not relevant:
        return None
    text = {
        "en": "The supplied brochure contains conflicting figures on page 17 for the minimum increase/decrease in sum insured. The Chinese text lists US$5,000 / HK$40,000 / MOP400,000; the English text lists US$5,000 / HK$400,000 / MOP40,000. I cannot choose or correct one version. Ask the insurer to confirm the applicable amount before relying on it. [S1]",
        "zh-Hans": "所提供册子的第17页对增加或减少保障额的最低金额有中英文冲突：中文列出5,000美元／40,000港元／400,000澳门元；英文列出5,000美元／400,000港元／40,000澳门元。我不能自行选择或更正其中一个版本，请先向保险公司确认适用金额。 [S1]",
        "zh-Hant": "所提供冊子的第17頁對增加或減少保障額的最低金額有中英文衝突：中文列出5,000美元／40,000港元／400,000澳門元；英文列出5,000美元／400,000港元／40,000澳門元。我不能自行選擇或更正其中一個版本，請先向保險公司確認適用金額。 [S1]",
    }[language]
    validated = validate_and_map_citations(text, relevant[:1])
    return ChatResponse(
        message=validated.text,
        citations=validated.citations,
        language=language,
        kind="insufficient",
        used_retrieval=True,
        notices=[localised_notice(language, "brochure_only")],
    )
