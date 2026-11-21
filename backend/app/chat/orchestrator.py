from __future__ import annotations

import logging
import re

from ..config import Settings
from ..guardrails.concepts import (
    concept_failure_notice,
    is_credentials_request,
    missing_concept_evidence,
)
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
from ..guardrails.policy import LANG_NAMES
from ..models import ChatRequest, ChatResponse
from ..retrieval.hybrid import HybridRetriever, RetrievalResult
from .llm import LLMError, LLMNotConfigured, OpenAICompatibleClient
from .prompts import build_messages, citation_repair_messages

logger = logging.getLogger(__name__)

HIGH_RISK_DETERMINATION = re.compile(
    r"\b(?:definitely|will|would|guarantee|guaranteed|must|entitled)\b"
    r".{0,45}\b(?:pay|payout|claim|cover|covered|eligible|approved|underwrit)\b|"
    r"\b(?:am i|are we|do i)\b.{0,30}\b(?:eligible|covered|entitled)\b|"
    r"(?:一定|保證|保证|必定).{0,25}(?:賠|赔|付|承保|合資格|合资格)|"
    r"(?:我|本人).{0,20}(?:合資格|合资格|受保|索償|索偿)",
    re.IGNORECASE | re.DOTALL,
)


def _attach_source_markers(text: str, hits: list) -> str:
    """Attach only evidence that is directly relevant to a fixed response."""
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

    def _nofact(
        self,
        language: str,
        retrieval: RetrievalResult | None = None,
        extra_notice: str | None = None,
        kind: str = "insufficient",
    ) -> ChatResponse:
        notices = [localised_notice(language, "brochure_only")]
        if extra_notice:
            notices.append(extra_notice)
        return ChatResponse(
            message=fixed_response(language, "insufficient"),
            language=language,
            kind=kind,
            used_retrieval=retrieval is not None,
            retrieval_mode=retrieval.mode if retrieval else None,
            confidence=retrieval.confidence if retrieval else None,
            notices=notices,
        )

    async def answer(self, request: ChatRequest) -> ChatResponse:
        decision = screen_input(request.message)
        language = request.language

        if is_credentials_request(request.message):
            return ChatResponse(
                message=fixed_response(language, "injection"),
                language=language,
                kind="blocked",
                notices=[localised_notice(language, "educational")],
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

        history = self._history_user_messages(request)
        retrieval_query = (
            f"policy features benefits risks fees suitability {request.message}"
            if decision.intent == Intent.ADVICE
            else request.message
        )
        retrieval = self.retriever.search(retrieval_query, history=history)

        if HIGH_RISK_DETERMINATION.search(request.message):
            return ChatResponse(
                message=fixed_response(language, "sensitive_redirect"),
                language=language,
                kind="insufficient",
                notices=[
                    localised_notice(language, "brochure_only"),
                    localised_notice(language, "sensitive"),
                ],
            )

        if decision.intent == Intent.UNSUPPORTED_CALCULATION:
            return self._vetted_calculation(language, retrieval)

        if not retrieval.sufficient:
            logger.info(
                "Low-confidence retrieval for question (top=%.3f mode=%s)",
                retrieval.confidence,
                retrieval.mode,
            )
            return self._nofact(
                language,
                retrieval,
                extra_notice=localised_notice(language, "professional"),
            )

        concept_gap = missing_concept_evidence(request.message, retrieval.hits)
        if concept_gap:
            logger.info("Concept evidence gap: %s", concept_gap)
            return self._nofact(
                language,
                retrieval,
                extra_notice=concept_failure_notice(language),
            )

        if decision.intent == Intent.ADVICE:
            return await self._advice_answer(
                request, retrieval, decision.sensitive_topics
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
                ],
            )

        messages = build_messages(
            language,
            request.message,
            retrieval.hits,
            request.history,
            decision.sensitive_topics,
            max_history_turns=self.settings.max_history_turns,
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
                    citation_repair_messages(
                        messages, draft=response.text, error=claim_issue or "citation"
                    ),
                    temperature=0.0,
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
                    return self._nofact(language, retrieval)
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
                    localised_notice(language, "provider_unavailable"),
                ],
            )
        except Exception:
            # Do not turn programming/configuration faults into fabricated model
            # answers. Provider faults are handled above; unexpected faults are
            # logged and surfaced as a safe insufficiency response.
            logger.exception("Unexpected answer-generation error")
            return self._nofact(language, retrieval)

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

    def _vetted_calculation(
        self, language: str, retrieval: RetrievalResult
    ) -> ChatResponse:
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

    async def _advice_answer(
        self,
        request: ChatRequest,
        retrieval: RetrievalResult,
        sensitive_topics: tuple[str, ...],
    ) -> ChatResponse:
        framing = advice_framing(request.language)
        if not self.llm.configured:
            return self._offline_advice(request, retrieval, sensitive_topics, framing)
        messages = build_messages(
            request.language,
            request.message,
            retrieval.hits,
            request.history,
            sensitive_topics,
            max_history_turns=self.settings.max_history_turns,
        )
        messages[0]["content"] += (
            "\nThe user asked for personalized advice. Start by explaining that "
            "suitability depends on their circumstances, then give an educational "
            "discussion of relevant brochure features and risks. Do not answer "
            "'yes' or 'no' to whether they should buy. End by encouraging a "
            "licensed professional consultation. Never assert that the user "
            "personally qualifies for a feature or will receive a particular benefit."
        )
        try:
            response = await self.llm.complete(messages)
            validated = validate_and_map_citations(
                response.text,
                retrieval.hits,
                {h.chunk.id for h in retrieval.hits},
            )
            issue = validate_answer_claims(validated.text, retrieval.hits)
            if (
                not has_any_citation(validated.text)
                or validated.had_invalid
                or issue
            ):
                raise LLMError(f"Invalid advice response: {issue or 'citation'}")
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
            return self._offline_advice(request, retrieval, sensitive_topics, framing)

    def _offline_advice(
        self,
        request: ChatRequest,
        retrieval: RetrievalResult,
        sensitive_topics: tuple[str, ...],
        framing: str,
    ) -> ChatResponse:
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

