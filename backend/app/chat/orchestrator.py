from __future__ import annotations

import logging
import re
from threading import Lock

from starlette.concurrency import run_in_threadpool

from ..config import Settings
from ..guardrails.concepts import is_credentials_request, missing_concept_evidence
from ..guardrails.grounding import (
    GroundingError,
    applicability_question,
    draft_failure_reasons,
    inspect_draft,
    literal_applicable,
    normalize_question_wording,
    review_approved,
    review_messages,
)
from ..guardrails.offline import render_offline_answer
from ..guardrails.output import validate_and_map_citations
from ..guardrails.policy import (
    Intent,
    advice_framing,
    fixed_response,
    localised_notice,
    screen_input,
)
from ..guardrails.source_conflicts import source_conflict_response
from ..models import ChatRequest, ChatResponse
from ..retrieval.hybrid import HybridRetriever, RetrievalHit, RetrievalResult
from .llm import LLMError, LLMInputTooLarge, LLMQuotaExceeded, OpenAICompatibleClient
from .language import normalize_generated_script
from .prompts import build_messages, citation_repair_messages

logger = logging.getLogger(__name__)
HIGH_RISK_DETERMINATION = re.compile(
    r"\b(?:definitely|will|would|guarantee|guaranteed|must|entitled)\b"
    r".{0,45}\b(?:payout|claim|cover|covered|eligible|approved|underwrit)\b|"
    # A policyholder paying a disclosed fee is different from the insurer
    # promising to pay a claim. Require the payer for the ambiguous verb pay.
    r"\b(?:insurer|insurance company|company|plan|policy)\s+"
    r"(?:(?:will|would|must)\s+(?:(?:definitely|always|certainly)\s+)?|"
    r"guarantee[sd]?\s+to\s+)pay\b|"
    r"\b(?:will|would|must)\s+(?:(?:the|this|my)\s+)?"
    r"(?:insurer|insurance company|company|plan|policy)\s+"
    r"(?:(?:definitely|always|certainly)\s+)?pay\b|"
    r"\b(?:am i|are we|do i)\b.{0,30}\b(?:eligible|covered|entitled)\b|"
    r"(?:一定|保證|保证|必定).{0,25}(?:賠|赔|付|承保|合資格|合资格)|"
    r"(?:我|本人).{0,20}(?:是否|能否|可否|可以|能|會否|会否|會不會|会不会|會|会)"
    r".{0,8}(?:合資格|合资格|受保|索償|索偿|獲賠|获赔)|"
    r"(?:我|本人)(?:合資格|合资格|受保)(?:嗎|吗|[?？])",
    re.IGNORECASE | re.DOTALL,
)


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
        # ONNX failure changes backend availability; serialize that state while
        # running all CPU work away from the async HTTP event loop.
        self._retrieval_lock = Lock()

    def _retrieve(self, query: str, history: list[str]) -> RetrievalResult:
        with self._retrieval_lock:
            return self.retriever.search(query, history=history)

    def _nofact(
        self,
        language: str,
        retrieval: RetrievalResult | None = None,
        extra_notice: str | None = None,
        *,
        generation_unverified: bool = False,
    ) -> ChatResponse:
        notices = [localised_notice(language, "brochure_only")]
        if extra_notice:
            notices.append(extra_notice)
        return ChatResponse(
            message=(
                localised_notice(language, "generation_unverified")
                if generation_unverified
                else fixed_response(language, "insufficient")
            ),
            language=language,
            kind="insufficient",
            used_retrieval=retrieval is not None,
            retrieval_mode=retrieval.mode if retrieval else None,
            confidence=retrieval.confidence if retrieval else None,
            notices=notices,
        )

    def _excerpts(
        self,
        request: ChatRequest,
        retrieval: RetrievalResult,
        sensitive_topics: tuple[str, ...],
        *,
        advice: bool = False,
        provider_unavailable: bool = False,
    ) -> ChatResponse:
        if not literal_applicable(
            applicability_question(
                request.message,
                [t.content for t in request.history if t.role == "user"],
            ),
            retrieval.hits,
            advice=advice,
        ):
            return self._nofact(request.language, retrieval)
        text = render_offline_answer(request.language, retrieval.hits, sensitive_topics)
        validated = validate_and_map_citations(text, retrieval.hits)
        framing = advice_framing(request.language) + "\n\n" if advice else ""
        notices = [localised_notice(request.language, "educational")]
        if advice:
            notices.append(localised_notice(request.language, "professional"))
        if provider_unavailable:
            notices.append(localised_notice(request.language, "provider_unavailable"))
        return ChatResponse(
            message=framing + validated.text,
            citations=validated.citations,
            language=request.language,
            kind="advice" if advice else "answer",
            used_retrieval=True,
            retrieval_mode=retrieval.mode,
            confidence=retrieval.confidence,
            notices=notices,
        )

    async def answer(self, request: ChatRequest) -> ChatResponse:
        decision = screen_input(request.message)
        language = request.language
        if is_credentials_request(request.message) or decision.intent in {
            Intent.EMPTY,
            Intent.INJECTION,
        }:
            return ChatResponse(
                message=fixed_response(
                    language,
                    "empty" if decision.intent == Intent.EMPTY else "injection",
                ),
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
        history = [
            turn.content
            for turn in request.history[-self.settings.max_history_turns :]
            if turn.role == "user"
        ]
        advice = decision.intent == Intent.ADVICE
        contextual_question = applicability_question(request.message, history)
        query = (
            f"policy features benefits risks fees suitability {contextual_question}"
            if advice
            else normalize_question_wording(contextual_question)
        )
        retrieval = await run_in_threadpool(self._retrieve, query, history)
        # The conflict belongs to reviewed source bytes, not to whichever
        # passage happened to rank first. Inspect the fingerprinted corpus.
        corpus_hits = [RetrievalHit(c, 0.0, 0.0, 0.0) for c in self.retriever.chunks]
        conflict = source_conflict_response(contextual_question, language, corpus_hits)
        if conflict:
            conflict.retrieval_mode = retrieval.mode
            return conflict
        if decision.intent == Intent.UNSUPPORTED_CALCULATION:
            # The refusal itself makes no product-specific numerical claim;
            # avoid inventing a citation-to-refusal relationship.
            return ChatResponse(
                message=fixed_response(language, "calculation"),
                language=language,
                kind="insufficient",
                used_retrieval=True,
                retrieval_mode=retrieval.mode,
                notices=[localised_notice(language, "brochure_only")],
            )
        if not retrieval.sufficient or missing_concept_evidence(
            request.message, retrieval.hits
        ):
            return self._nofact(language, retrieval)
        # Distinctive unsupported question anchors must not be drowned out by
        # generic words such as policy/cover/benefit. The semantic reviewer is
        # an additional gate, not a substitute for basic applicability.
        if not literal_applicable(
            applicability_question(
                request.message,
                [t.content for t in request.history if t.role == "user"],
            ),
            retrieval.hits,
            advice=advice,
        ):
            return self._nofact(language, retrieval)
        if not self.llm.configured:
            return self._excerpts(
                request, retrieval, decision.sensitive_topics, advice=advice
            )
        messages = build_messages(
            language,
            request.message,
            retrieval.hits,
            request.history,
            decision.sensitive_topics,
            max_history_turns=self.settings.max_history_turns,
        )
        if advice:
            messages[0]["content"] += (
                "\nExplain only cited product trade-offs. Do not make a personal recommendation. "
                "The application adds suitability framing and a professional referral."
            )
        # At most three provider calls: draft, optional deterministic repair,
        # independent review. Never retry a reviewer or a provider/quota error.
        try:
            response = await self.llm.complete(messages)
        except (LLMQuotaExceeded, LLMInputTooLarge):
            raise
        except LLMError:
            return self._excerpts(
                request,
                retrieval,
                decision.sensitive_topics,
                advice=advice,
                provider_unavailable=True,
            )
        try:
            draft = await run_in_threadpool(normalize_generated_script, response.text, language)
            try:
                claims = inspect_draft(draft, retrieval.hits)
            except GroundingError as exc:
                logger.info("Generated draft requires repair: %s", exc)
                errors = await run_in_threadpool(
                    draft_failure_reasons, draft, retrieval.hits, str(exc)
                )
                repaired = await self.llm.complete(
                    citation_repair_messages(
                        messages, draft=draft, error=", ".join(errors)
                    ),
                    temperature=0.0,
                )
                draft = await run_in_threadpool(normalize_generated_script, repaired.text, language)
                claims = inspect_draft(draft, retrieval.hits)
            review = await self.llm.complete(
                review_messages(
                    request.message, language, claims, retrieval.hits, history=history
                ),
                temperature=0.0,
            )
            if not review_approved(review.text, claims):
                logger.warning("Generated explanation withheld: grounding review rejected draft")
                return self._nofact(language, retrieval, generation_unverified=True)
        except (LLMQuotaExceeded, LLMInputTooLarge):
            raise
        except GroundingError as exc:
            logger.warning("Generated explanation withheld: %s", exc)
            return self._nofact(language, retrieval, generation_unverified=True)
        except LLMError:
            logger.warning("Generation repair or review unavailable; returning source excerpts")
            return self._excerpts(
                request, retrieval, decision.sensitive_topics,
                advice=advice, provider_unavailable=True,
            )
        except Exception:
            logger.exception("Unexpected grounding/review failure")
            return self._nofact(language, retrieval, generation_unverified=True)
        validated = validate_and_map_citations(draft, retrieval.hits)
        notices = [localised_notice(language, "educational")]
        if advice:
            notices.append(localised_notice(language, "professional"))
        if decision.sensitive_topics:
            notices.append(localised_notice(language, "sensitive"))
        return ChatResponse(
            message=(advice_framing(language) + "\n\n" if advice else "")
            + validated.text,
            model_generated=True,
            citations=validated.citations,
            language=language,
            kind="advice" if advice else "answer",
            used_retrieval=True,
            retrieval_mode=retrieval.mode,
            confidence=retrieval.confidence,
            notices=notices,
        )
