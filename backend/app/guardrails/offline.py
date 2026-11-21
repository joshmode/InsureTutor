from __future__ import annotations

"""Evidence-first deterministic fallback used when the LLM is unavailable."""

from ..retrieval.hybrid import RetrievalHit


def render_offline_answer(
    language: str,
    hits: list[RetrievalHit],
    sensitive_topics: tuple[str, ...] = (),
    *,
    explanation_failed: bool = False,
) -> str:
    if not hits:
        return ""
    lines = {
        "en": (
            "The tutoring model is not available, so I can only show the relevant "
            "brochure excerpts rather than write a full explanation:"
        ),
        "zh-Hans": "教学模型暂时不可用，我只能向您展示册子中的相关原文，而不能生成完整解释：",
        "zh-Hant": "教學模型暫時不可用，我只能向您展示冊子中的相關原文，而不能生成完整解釋：",
    }.get(language, "")
    if explanation_failed:
        lines = {
            "en": "I couldn’t produce a verified explanation this time. Here are the relevant brochure passages:",
            "zh-Hans": "这次未能生成经核实的解释。以下是相关册子原文：",
            "zh-Hant": "這次未能生成經核實的解釋。以下是相關冊子原文：",
        }.get(language, lines)
    result = [lines]
    for index, hit in enumerate(hits[:4], start=1):
        excerpt = " ".join(hit.chunk.citation_excerpt.split())
        if len(excerpt) > 380:
            excerpt = excerpt[:377].rstrip() + "…"
        result.append(f"- {excerpt} [S{index}]")
    if sensitive_topics:
        result.append(
            {
                "en": (
                    "For medical, tax, legal, underwriting or claims-dispute matters, "
                    "confirm the position with the insurer or a qualified professional."
                ),
                "zh-Hans": "如涉及医疗、税务、法律、核保或理赔争议，请向保险公司或合资格专业人士确认。",
                "zh-Hant": "如涉及醫療、稅務、法律、核保或理賠爭議，請向保險公司或合資格專業人士確認。",
            }.get(language, "")
        )
    return "\n\n".join(result)

