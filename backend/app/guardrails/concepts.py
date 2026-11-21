from __future__ import annotations

from ..retrieval.hybrid import RetrievalHit


def is_credentials_request(text: str) -> bool:
    lowered = text.lower()
    return any(
        phrase in lowered
        for phrase in (
            "api key",
            "access token",
            "secret key",
            "password",
            "credentials",
            "api 密鑰",
            "api 密钥",
            "密碼",
            "密码",
        )
    )


def missing_concept_evidence(message: str, hits: list[RetrievalHit]) -> str | None:
    """Detect questions that need a concept which is absent from the brochure.

    This is intentionally narrow and observable. The general "minimum support"
    threshold already handles unknown topics; here we protect high-risk
    relational questions where a keyword match could otherwise tempt the model
    to infer an answer from adjacent product terms.
    """
    lowered = message.lower()
    combined = " ".join(
        f"{hit.chunk.section} {hit.chunk.citation_excerpt}" for hit in hits
    ).lower()
    # Detailed rider waiting periods cannot be inferred from a rider name.
    if any(term in lowered for term in ("waiting period", "等候期", "等待期")):
        if not any(term in combined for term in ("waiting period", "等候期", "等待期")):
            return "no_waiting_period_evidence"
    if any(term in lowered for term in ("inflation-linked", "inflation linked", "抗通脹", "抗通胀")):
        if "inflation-linked" not in combined:
            return "no_inflation_linked_product_evidence"
    if any(term in lowered for term in ("premium waiver", "豁免保費計劃", "豁免保费计划")):
        if "waiver of premium" not in combined and "豁免保費" not in combined and "豁免保费" not in combined:
            return "no_waiver_evidence"
    if any(term in lowered for term in ("critical illness", "嚴重疾病", "严重疾病")):
        if "critical illness" not in combined and "嚴重疾病" not in combined and "严重疾病" not in combined:
            return "no_critical_illness_evidence"
    if any(term in lowered for term in ("accident benefit", "意外保障")):
        if "accident benefit" not in combined and "意外保障" not in combined:
            return "no_accident_evidence"
    return None


def concept_failure_notice(language: str) -> str:
    return {
        "en": (
            "I couldn’t find a passage in the supplied brochure that establishes "
            "that specific point. I won’t infer it from a related term."
        ),
        "zh-Hans": (
            "我在所提供的册子中找不到能够确定这一点的段落，因此不会仅凭相关词语推断。"
        ),
        "zh-Hant": (
            "我在所提供的冊子中找不到能夠確定這一點的段落，因此不會僅憑相關詞語推斷。"
        ),
    }.get(language, "")

