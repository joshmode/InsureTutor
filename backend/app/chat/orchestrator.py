from __future__ import annotations

import logging

from ..config import Settings
from ..guardrails.offline import render_offline_answer
from ..guardrails.output import (
    has_any_citation,
    validate_and_map_citations,
    validate_answer_claims,
)
from ..guardrails.policy import (
    Intent,
    advice_framing,
    fixed_response,
    localised_notice,
    screen_input,
)
from ..models import ChatRequest, ChatResponse
from ..retrieval.hybrid import HybridRetriever, RetrievalResult
from .llm import LLMError, LLMNotConfigured, OpenAICompatibleClient
from .prompts import build_messages, citation_repair_messages

logger = logging.getLogger(__name__)


def _attach_source_markers(text: str, hits: list) -> str:
    """Attach the two most relevant evidence passages to a deterministic answer."""
    if not hits:
        return text
    markers = "".join(f"[S{index}]" for index in range(1, min(2, len(hits)) + 1))
    return f"{text} {markers}"


class ChatOrchestrator:
    def __init__(
        self,
        settings: Settings,
        retriever: HybridRetriever,
        llm: OpenAICompatibleClient,
    ):
        self.settings = settings
        self.retriever = retriever
        self.llm = llm

    def _history_user_messages(self, request: ChatRequest) -> list[str]:
        users = [
            turn.content
            for turn in request.history[-self.settings.max_history_turns :]
            if turn.role == "user"
        ]
        return users

    async def answer(self, request: ChatRequest) -> ChatResponse:
        decision = screen_input(request.message)
        language = request.language
        if decision.intent == Intent.ADVICE:
            advice_retrieval = self.retriever.search(
                "policy risks costs benefits suitability general information",
                history=self._history_user_messages(request),
            )
            return await self._advice_answer(
                request,
                advice_retrieval,
                decision.sensitive_topics,
            )
        if decision.intent == Intent.EMPTY:
            return ChatResponse(
                message=fixed_response(language, "empty"),
                language=language,
                kind="blocked",
            )
        if decision.intent == Intent.INJECTION:
            return ChatResponse(
                message=fixed_response(language, "injection"),
                language=language,
                kind="blocked",
                notices=[localised_notice(language, "educational")],
            )
        if decision.intent == Intent.UNRELATED:
            return ChatResponse(
                message=fixed_response(language, "unrelated"),
                language=language,
                kind="scope",
                notices=[localised_notice(language, "educational")],
            )

        retrieval = self.retriever.search(
            request.message,
            history=self._history_user_messages(request),
        )

        if decision.intent == Intent.UNSUPPORTED_CALCULATION:
            text = fixed_response(language, "calculation")
            validated = validate_and_map_citations(
                _attach_source_markers(text, retrieval.hits),
                retrieval.hits,
                {h.chunk.id for h in retrieval.hits},
            )
            return ChatResponse(
                message=validated.text,
                citations=validated.citations,
                language=language,
                kind="insufficient",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[localised_notice(language, "brochure_only")],
            )

        if not retrieval.sufficient:
            logger.info(
                "Low-confidence retrieval for question (top=%.3f mode=%s)",
                retrieval.confidence,
                retrieval.mode,
            )
            return ChatResponse(
                message=fixed_response(language, "insufficient"),
                language=language,
                kind="insufficient",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[
                    localised_notice(language, "brochure_only"),
                    localised_notice(language, "professional"),
                ],
            )

        if not self.llm.configured:
            offline = render_offline_answer(
                language, retrieval.hits, decision.sensitive_topics
            )
            validated = validate_and_map_citations(
                offline, retrieval.hits, {h.chunk.id for h in retrieval.hits}
            )
            return ChatResponse(
                message=validated.text,
                citations=validated.citations,
                language=language,
                kind="answer",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[
                    localised_notice(language, "educational"),
                    "LLM_API_KEY is not configured; showing source excerpts only.",
                ],
            )

        messages = build_messages(
            language,
            request.message,
            retrieval.hits,
            request.history,
            decision.sensitive_topics,
        )
        try:
            response = await self.llm.complete(messages)
            validated = validate_and_map_citations(
                response.text,
                retrieval.hits,
                {h.chunk.id for h in retrieval.hits},
            )
            claim_issue = validate_answer_claims(validated.text, retrieval.hits)
            if (
                not has_any_citation(validated.text)
                or validated.had_invalid
                or claim_issue
            ):
                logger.warning(
                    "Answer validation failed (%s); retrying with a constrained prompt",
                    claim_issue or "citation",
                )
                repaired = await self.llm.complete(
                    citation_repair_messages(messages), temperature=0.0
                )
                validated = validate_and_map_citations(
                    repaired.text,
                    retrieval.hits,
                    {h.chunk.id for h in retrieval.hits},
                )
                if (
                    not has_any_citation(validated.text)
                    or validated.had_invalid
                    or validate_answer_claims(validated.text, retrieval.hits)
                ):
                    logger.error("Citation repair failed; returning safe fallback")
                    return ChatResponse(
                        message=fixed_response(language, "insufficient"),
                        language=language,
                        kind="insufficient",
                        used_retrieval=True,
                        retrieval_mode=retrieval.mode,
                        confidence=retrieval.confidence,
                        notices=[localised_notice(language, "brochure_only")],
                    )
        except (LLMError, LLMNotConfigured) as exc:
            logger.warning("LLM request failed: %s", exc)
            offline = render_offline_answer(
                language, retrieval.hits, decision.sensitive_topics
            )
            validated = validate_and_map_citations(
                offline, retrieval.hits, {h.chunk.id for h in retrieval.hits}
            )
            return ChatResponse(
                message=validated.text,
                citations=validated.citations,
                language=language,
                kind="answer",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[
                    localised_notice(language, "educational"),
                    "The model provider was unavailable; showing source excerpts only.",
                ],
            )

        notices = [localised_notice(language, "educational")]
        if decision.sensitive_topics:
            notices.append(localised_notice(language, "sensitive"))
        return ChatResponse(
            message=validated.text,
            citations=validated.citations,
            language=language,
            kind="answer",
            used_retrieval=True,
            retrieval_mode=retrieval.mode,
            confidence=retrieval.confidence,
            notices=notices,
        )

    async def _advice_answer(
        self,
        request: ChatRequest,
        retrieval: RetrievalResult,
        sensitive_topics: tuple[str, ...],
    ) -> ChatResponse:
        framing = advice_framing(request.language)
        if not self.llm.configured:
            offline = render_offline_answer(
                request.language, retrieval.hits, sensitive_topics
            )
            validated = validate_and_map_citations(
                offline, retrieval.hits, {h.chunk.id for h in retrieval.hits}
            )
            return ChatResponse(
                message=f"{framing}\n\n{validated.text}",
                citations=validated.citations,
                language=request.language,
                kind="advice",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[
                    localised_notice(request.language, "educational"),
                    localised_notice(request.language, "professional"),
                ],
            )
        messages = build_messages(
            request.language,
            request.message,
            retrieval.hits,
            request.history,
            sensitive_topics,
        )
        messages[0]["content"] += (
            "\nThe user asked for personalized advice. Start by explaining that "
            "suitability depends on their circumstances, then give an educational "
            "discussion of relevant brochure features and risks. Do not answer "
            "'yes' or 'no' to whether they should buy. End by encouraging a "
            "licensed professional consultation."
        )
        try:
            response = await self.llm.complete(messages)
            validated = validate_and_map_citations(
                response.text,
                retrieval.hits,
                {h.chunk.id for h in retrieval.hits},
            )
            if (
                not has_any_citation(validated.text)
                or validated.had_invalid
                or validate_answer_claims(validated.text, retrieval.hits)
            ):
                raise LLMError("Invalid citations in advice response")
            return ChatResponse(
                message=validated.text,
                citations=validated.citations,
                language=request.language,
                kind="advice",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[
                    localised_notice(request.language, "educational"),
                    localised_notice(request.language, "professional"),
                ],
            )
        except LLMError:
            offline = render_offline_answer(
                request.language, retrieval.hits, sensitive_topics
            )
            validated = validate_and_map_citations(
                offline, retrieval.hits, {h.chunk.id for h in retrieval.hits}
            )
            return ChatResponse(
                message=f"{framing}\n\n{validated.text}",
                citations=validated.citations,
                language=request.language,
                kind="advice",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                confidence=retrieval.confidence,
                notices=[
                    localised_notice(request.language, "educational"),
                    localised_notice(request.language, "professional"),
                ],
            )

