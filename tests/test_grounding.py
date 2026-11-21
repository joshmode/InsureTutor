from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.chat.llm import LLMError, LLMQuotaExceeded
from backend.app.chat.orchestrator import ChatOrchestrator
from backend.app.config import Settings
from backend.app.guardrails.grounding import (
    GroundingError,
    inspect_draft,
    literal_applicable,
    review_approved,
)
from backend.app.ingestion.chunker import Chunk
from backend.app.models import ChatRequest
from backend.app.retrieval.hybrid import RetrievalHit, RetrievalResult


def hit(text, id="one"):
    return RetrievalHit(Chunk(id, "source.pdf", 1, "Source", text), 1, 1, 0)


HITS = [
    hit("Administrative charge is US$4 monthly. Withdrawal charge is US$25."),
    hit("A withdrawal charge is US$200 under a different condition.", "two"),
]
DRAFT = "The administrative charge is US$4 monthly. [S1]"
APPROVAL = json.dumps(
    {
        "applicable": True,
        "safe": True,
        "language_correct": True,
        "claims": [{"id": 1, "supported": True}],
    }
)


class ScriptedLLM:
    configured = True

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages, **kwargs):
        self.calls.append(messages)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return SimpleNamespace(text=response)


class StaticRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.chunks = [h.chunk for h in hits]

    def search(self, *args, **kwargs):
        return RetrievalResult(self.hits, True, "lexical", 1, [args[0]])


def orchestrator(responses, hits=HITS):
    return ChatOrchestrator(
        Settings(_env_file=None), StaticRetriever(hits), ScriptedLLM(responses)
    )


def test_each_sentence_needs_its_own_citation():
    with pytest.raises(GroundingError, match="uncited_claim"):
        inspect_draft(DRAFT + " Your principal can never fall.", HITS)


def test_number_must_occur_in_the_claims_own_cited_source():
    with pytest.raises(GroundingError, match="unsupported_numeric_claim"):
        inspect_draft("The withdrawal charge is US$200. [S1]", HITS)


def test_direct_quote_must_exist_in_its_own_source():
    with pytest.raises(GroundingError, match="unsupported_quote"):
        inspect_draft('The brochure says "every withdrawal is free". [S1]', HITS)


@pytest.mark.parametrize(
    "review",
    [
        "sure",
        "{}",
        "```json\n" + APPROVAL + "\n```",
        APPROVAL.replace('"applicable": true', '"applicable": false'),
        APPROVAL.replace('"safe": true', '"safe": "true"'),
        APPROVAL.replace('"id": 1', '"id": 2'),
    ],
)
def test_reviewer_requires_exact_complete_true_verdicts(review):
    assert not review_approved(review, inspect_draft(DRAFT, HITS))


def test_multiple_claims_and_repeated_source_are_scoped_separately():
    claims = inspect_draft(DRAFT + "\nThe withdrawal charge is US$200. [S2]", HITS)
    assert [c.sources for c in claims] == [(1,), (2,)]
    assert not review_approved(APPROVAL, claims)


def test_generated_answer_requires_separate_review():
    app = orchestrator([DRAFT, APPROVAL])
    answer = asyncio.run(
        app.answer(ChatRequest(message="What is the administrative charge?"))
    )
    assert answer.kind == "answer" and "US$4" in answer.message
    assert len(app.llm.calls) == 2
    review = json.loads(app.llm.calls[1][1]["content"])
    assert review["claims"][0]["evidence"][0]["source"] == "S1"
    assert "different condition" not in review["claims"][0]["evidence"][0]["excerpt"]


@pytest.mark.parametrize(
    "review",
    [
        "{}",
        LLMError("reviewer unavailable"),
        APPROVAL.replace('"supported": true', '"supported": false'),
    ],
)
def test_reviewer_failure_or_unsupported_claim_fails_closed(review):
    app = orchestrator([DRAFT, review])
    answer = asyncio.run(
        app.answer(ChatRequest(message="What is the administrative charge?"))
    )
    assert answer.kind == "insufficient"
    assert "US$4" not in answer.message
    assert not answer.citations
    assert len(app.llm.calls) == 2


def test_matching_number_is_not_enough_for_semantic_approval():
    # Four dollars exists, but it is an admin charge, not a guaranteed payout.
    app = orchestrator(
        [
            "The guaranteed death benefit is US$4. [S1]",
            APPROVAL.replace('"supported": true', '"supported": false'),
        ]
    )
    answer = asyncio.run(
        app.answer(ChatRequest(message="Explain the administrative charge."))
    )
    assert answer.kind == "insufficient"


def test_quota_exhaustion_does_not_retry_or_generate_excerpts():
    app = orchestrator([LLMQuotaExceeded("no allowance")])
    with pytest.raises(LLMQuotaExceeded):
        asyncio.run(
            app.answer(ChatRequest(message="What is the administrative charge?"))
        )
    assert len(app.llm.calls) == 1


@pytest.mark.parametrize(
    "question",
    [
        "Does this policy cover earthquake damage to my house?",
        "Does this policy cover flooding damage to my apartment?",
        "Does this policy cover stolen bicycle repairs?",
    ],
)
def test_missing_distinctive_anchors_reject_unrelated_risks_without_blacklist(question):
    app = orchestrator(
        [], [hit("Life insurance offers a death benefit to the beneficiary.")]
    )
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "insufficient" and not answer.citations
    assert app.llm.calls == []


def test_no_provider_also_rejects_irrelevant_excerpts():
    app = orchestrator(
        [], [hit("Life insurance offers a death benefit to the beneficiary.")]
    )
    app.llm.configured = False
    answer = asyncio.run(
        app.answer(
            ChatRequest(message="Does this policy cover earthquake damage to my house?")
        )
    )
    assert answer.kind == "insufficient"
    assert not answer.citations


@pytest.mark.parametrize(
    "language,question",
    [
        ("en", "What is the minimum increase/decrease amount in sum insured?"),
        ("zh-Hans", "增加保障额的最低金额是多少？"),
        ("zh-Hant", "增加保障額的最低金額是多少？"),
    ],
)
def test_reviewed_source_conflict_never_chooses_a_currency_figure(
    knowledge_chunks, language, question
):
    app = orchestrator([], [RetrievalHit(c, 1, 1, 0) for c in knowledge_chunks])
    answer = asyncio.run(app.answer(ChatRequest(message=question, language=language)))
    assert answer.kind == "insufficient" and len(answer.citations) == 1
    assert answer.citations[0].page == 17
    assert "400,000" in answer.message and "40,000" in answer.message
    assert app.llm.calls == []


def test_retrieval_is_offloaded_and_serialized():
    import threading
    import time

    class SlowRetriever(StaticRetriever):
        active = 0

        def search(self, *args, **kwargs):
            assert threading.current_thread() is not threading.main_thread()
            self.active += 1
            assert self.active == 1
            time.sleep(0.04)
            self.active -= 1
            return super().search(*args, **kwargs)

    app = orchestrator([])
    app.retriever = SlowRetriever(HITS)
    app.llm.configured = False

    async def run():
        tasks = [
            asyncio.create_task(
                app.answer(ChatRequest(message="What is the administrative charge?"))
            )
            for _ in range(2)
        ]
        ticks = 0
        while not all(t.done() for t in tasks):
            ticks += 1
            await asyncio.sleep(0.005)
        return ticks, await asyncio.gather(*tasks)

    ticks, answers = asyncio.run(run())
    assert ticks >= 5 and all(a.citations for a in answers)


def test_all_twelve_frontend_starters_keep_offline_sources(retriever):
    import re

    # Read the actual localized product prompts, so UI wording changes exercise
    # the applicability boundary instead of a copied approximation.
    source = Path("frontend/src/lib/i18n.ts").read_text()
    questions = [
        json.loads(value)
        for value in re.findall(r'prompt:\s*("(?:[^"\\]|\\.)*")', source)
    ]
    assert len(questions) == 12
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False

    async def run():
        return [await app.answer(ChatRequest(message=q)) for q in questions]

    answers = asyncio.run(run())
    assert all(a.kind == "answer" and a.citations for a in answers)


@pytest.mark.parametrize(
    "question",
    [
        "Can I increase my premium payments?",
        "What is the minimum increase in periodic withdrawal amount?",
    ],
)
def test_sum_insured_conflict_does_not_hijack_other_increases(
    knowledge_chunks, question
):
    from backend.app.guardrails.source_conflicts import source_conflict_response

    hits = [RetrievalHit(c, 1, 1, 0) for c in knowledge_chunks]
    assert source_conflict_response(question, "en", hits) is None


def test_followup_context_is_reused_only_when_no_new_topic_is_introduced(retriever):
    from backend.app.models import ChatTurn

    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False

    async def run():
        history = [ChatTurn(role="user", content="Is the 4% interest rate guaranteed?")]
        followup = await app.answer(
            ChatRequest(message="And what about that?", history=history)
        )
        switched = await app.answer(
            ChatRequest(
                message="And what about earthquake damage to my house?", history=history
            )
        )
        chinese = await app.answer(ChatRequest(message="那是什麼呢？", history=history))
        return followup, switched, chinese

    followup, switched, chinese = asyncio.run(run())
    assert followup.citations and chinese.citations
    assert switched.kind == "insufficient" and not switched.citations


@pytest.mark.parametrize(
    "question", ["What is the benefit term?", "What is the premium payment term?"]
)
def test_term_answer_quotes_its_own_label_and_age_100(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer"
    assert any(
        "To Age 100" in c.excerpt
        and question.split("the ")[1].rstrip("?").lower() in c.excerpt.lower()
        for c in answer.citations
    )
    assert "100" in answer.message


def test_plural_payment_modes_returns_actual_source_modes(retriever):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message="What are the payment modes?")))
    assert answer.kind == "answer"
    assert any(
        "Payment Mode" in c.excerpt and "Annual" in c.excerpt and "Monthly" in c.excerpt
        for c in answer.citations
    )


def test_plural_currencies_retains_hong_kong_policy_source(retriever):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(
        app.answer(ChatRequest(message="Which currencies can a Hong Kong policy use?"))
    )
    assert answer.kind == "answer"
    assert any(
        "US$" in c.excerpt and "HK$" in c.excerpt and "Hong Kong" in c.excerpt
        for c in answer.citations
    )
