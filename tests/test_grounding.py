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
        if callable(response):
            response = response(messages)
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


@pytest.mark.parametrize("needs_repair", [False, True])
def test_requested_script_is_normalized_before_review_and_after_repair(needs_repair):
    draft = "提款費用為US$25。 [S1]"
    responses = (["提款費用為US$25。", draft] if needs_repair else [draft]) + [APPROVAL]
    app = orchestrator(responses)
    answer = asyncio.run(app.answer(ChatRequest(message="What is the withdrawal charge?", language="zh-Hans")))
    assert answer.model_generated
    assert "提款费用为US$25" in answer.message
    reviewed = json.loads(app.llm.calls[-1][1]["content"])
    assert "提款费用为US$25" in reviewed["claims"][0]["text"]
    assert answer.citations[0].excerpt == HITS[0].chunk.citation_excerpt


def test_each_sentence_needs_its_own_citation():
    with pytest.raises(GroundingError, match="uncited_claim"):
        inspect_draft(DRAFT + " Your principal can never fall.", HITS)


@pytest.mark.parametrize("claim", [
    "A surrender charge may apply in the first 14 years on lapse, surrender, or decrease in Basic Sum Insured.",
    "A surrender **charge** may apply in the first 14 **years**.",
    "退保費用適用於首14年。",
    "退保费用适用于首14年。",
])
def test_surrender_duration_cannot_omit_the_restart_on_increased_cover(knowledge_chunks, claim):
    source = next(c for c in knowledge_chunks if c.page == 18 and "effective date of each increase" in c.citation_excerpt)
    with pytest.raises(GroundingError, match="missing_surrender_charge_start_events"):
        inspect_draft(claim + " [S1]", [RetrievalHit(source, 1, 1, 0)])


@pytest.mark.parametrize("claim", [
    "Surrender charges apply in the first 14 years from the Policy Date or the effective date of each increase in Basic Sum Insured.",
    "Surrender charges may apply in the first 14 years of each coverage layer.",
    "退保費用適用於保單日期或每次增加基本保障額的生效日期起計首14年。",
    "退保费用适用于保单日期或每次增加基本保障额的生效日期起计首14年。",
])
def test_surrender_duration_retains_both_source_start_events(knowledge_chunks, claim):
    source = next(c for c in knowledge_chunks if c.page == 18 and "effective date of each increase" in c.citation_excerpt)
    assert inspect_draft(claim + " [S1]", [RetrievalHit(source, 1, 1, 0)])


def test_duration_gate_does_not_invent_restart_terms_for_other_sources():
    assert inspect_draft("Surrender charges apply in the first 14 years. [S1]", [hit("Surrender charges apply in the first 14 years.")])


def test_surrender_start_events_can_span_adjacent_claims_from_the_same_source(knowledge_chunks):
    source = next(c for c in knowledge_chunks if c.page == 18 and "effective date of each increase" in c.citation_excerpt)
    draft = "Surrender charges apply in the first 14 years from the Policy Date. [S1]\nIt is also applicable in the first 14 years from the effective date of each increase in Basic Sum Insured. [S1]"
    assert len(inspect_draft(draft, [RetrievalHit(source, 1, 1, 0)])) == 2


@pytest.mark.parametrize("qualifier", [
    "It is also applicable in the first 14 years from the effective date of each increase in Basic Sum Insured. [S2]",
    "The maturity benefit lasts 14 years from the effective date of each increase in Basic Sum Insured. [S1]",
])
def test_another_source_or_benefit_cannot_supply_the_surrender_clock(knowledge_chunks, qualifier):
    source = next(c for c in knowledge_chunks if c.page == 18 and "effective date of each increase" in c.citation_excerpt)
    draft = "Surrender charges apply in the first 14 years from the Policy Date. [S1]\n" + qualifier
    with pytest.raises(GroundingError, match="missing_surrender_charge_start_events"):
        inspect_draft(draft, [RetrievalHit(source, 1, 1, 0), hit(source.citation_excerpt, "other")])


def test_one_repair_receives_all_independent_draft_failures(knowledge_chunks):
    source = next(c for c in knowledge_chunks if c.page == 18 and "effective date of each increase" in c.citation_excerpt)
    bad = "Here is the answer. Surrender charges apply in the first 14 years. [S1]"
    valid = "Surrender charges apply in the first 14 years from the Policy Date or the effective date of each increase in Basic Sum Insured. [S1]"

    def repair(messages):
        feedback = messages[-1]["content"]
        return valid if all(code in feedback for code in ("uncited_claim", "missing_surrender_charge_start_events")) else bad

    app = orchestrator([bad, repair, APPROVAL], [RetrievalHit(source, 1, 1, 0)])
    answer = asyncio.run(app.answer(ChatRequest(message="Explain surrender charges.", language="en")))
    assert answer.model_generated
    assert "effective date of each increase" in answer.message
    assert len(app.llm.calls) == 3


def test_number_must_occur_in_the_claims_own_cited_source():
    with pytest.raises(GroundingError, match="unsupported_numeric_claim"):
        inspect_draft("The withdrawal charge is US$200. [S1]", HITS)


@pytest.mark.parametrize("number", ["101", "101.5"])
def test_sentence_final_period_cannot_hide_an_unsupported_bare_number(number):
    with pytest.raises(GroundingError, match="unsupported_claim_number"):
        inspect_draft(f"The benefit term is {number}. [S1]", [hit("The benefit term is 100.")])


def test_sentence_final_decimal_value_keeps_its_complete_value():
    assert inspect_draft("The value is 100.50. [S1]", [hit("The value is 100.5.")])


@pytest.mark.parametrize(
    "draft",
    [
        "The withdrawal charge is US$4. [S1]",
        "The administrative charge is US$25. [S1]",
        "The **withdrawal charge** is US$4. [S1]",
        "The current withdrawal charge is US$4. [S1]",
        "The withdrawal fee is US$4. [S1]",
    ],
)
def test_same_source_number_cannot_be_reassigned_to_another_explicit_field(draft):
    with pytest.raises(GroundingError, match="unsupported_numeric_field"):
        inspect_draft(draft, HITS)


@pytest.mark.parametrize(
    "draft",
    [
        "The withdrawal charge is US$25. [S1]",
        "The administrative charge is US$4.00 monthly. [S1]",
    ],
)
def test_correct_explicit_field_and_amount_remain_accepted(draft):
    assert len(inspect_draft(draft, HITS)) == 1


def test_bare_footnote_after_field_label_is_not_a_monetary_value():
    evidence = [hit("Administrative charge 3\nUS$4 per month.")]
    assert len(inspect_draft(DRAFT, evidence)) == 1


def test_spaced_source_percent_is_the_same_unit_as_the_draft():
    assert inspect_draft("Base rate is 2.5%. [S1]", [hit("Base rate is 2.5 %.")])


@pytest.mark.parametrize("amount", ["US$25", "HK$200", "MOP200"])
@pytest.mark.parametrize("prefix", ["", "current "])
def test_actual_footnoted_withdrawal_charge_and_cross_source_label_swap(knowledge_chunks, amount, prefix):
    source = next(
        c for c in knowledge_chunks
        if c.page == 18 and "withdrawal charge10 of US$25" in c.citation_excerpt
    )
    # An unrelated amount is deliberately in the same cited evidence so the
    # ordinary number-membership check alone cannot catch a field swap.
    evidence = [hit(source.citation_excerpt + "\nAdministrative charge is US$4 monthly.")]
    assert inspect_draft(f"The {prefix}withdrawal charge is {amount}. [S1]", evidence)
    with pytest.raises(GroundingError, match="unsupported_numeric_field"):
        inspect_draft(f"The {prefix}withdrawal charge is US$4. [S1]", evidence)


@pytest.mark.parametrize(
    "draft",
    [
        "The periodic withdrawal charge is US$25. [S1]",
        "The withdrawal charge is US$0. [S1]",
    ],
)
def test_more_specific_field_cannot_borrow_an_amount_from_a_general_label(draft):
    evidence = [hit("Withdrawal charge is US$25. Periodic withdrawal charge is US$0.")]
    with pytest.raises(GroundingError, match="unsupported_numeric_field"):
        inspect_draft(draft, evidence)


def test_padded_label_cannot_swap_amounts_between_two_actual_brochure_citations(knowledge_chunks):
    withdrawal = next(c for c in knowledge_chunks if c.page == 18 and "withdrawal charge10 of US$25" in c.citation_excerpt)
    administrative = next(c for c in knowledge_chunks if c.page == 17 and "US$4" in c.citation_excerpt)
    evidence = [RetrievalHit(c, 1, 1, 0) for c in (withdrawal, administrative)]
    with pytest.raises(GroundingError, match="unsupported_numeric_field"):
        inspect_draft("The current withdrawal charge is US$4. [S1][S2]", evidence)


def test_direct_quote_must_exist_in_its_own_source():
    with pytest.raises(GroundingError, match="unsupported_quote"):
        inspect_draft('The brochure says "every withdrawal is free". [S1]', HITS)


@pytest.mark.parametrize(
    "claim",
    [
        "YF Life Insurance International Ltd. underwrites this plan.",
        "The assumed base rate is 4% p.a. and is not guaranteed.",
        "The brochure gives an example, e.g. a withdrawal.",
        "Mr. Chan illustrates the life protection options.",
    ],
)
def test_common_abbreviations_do_not_create_uncited_sentence_fragments(claim):
    claims = inspect_draft(claim + " [S1]", [hit(claim)])
    assert [entry.text for entry in claims] == [claim]


@pytest.mark.parametrize(
    "draft",
    [
        "The underwriter is YF Life Insurance International Ltd. [S1] Your principal can never fall.",
        "YF Life Insurance International Ltd. underwrites this plan. [S1] Your principal can never fall.",
    ],
)
def test_abbreviation_handling_keeps_the_next_uncited_sentence_separate(draft):
    with pytest.raises(GroundingError, match="uncited_claim"):
        inspect_draft(draft, [hit("YF Life Insurance International Ltd. underwrites this plan.")])


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
    "question",
    [
        "What is the reinstatement interest charge?",
        "What is the maternity death benefit?",
        "What is the ransomware withdrawal charge?",
        "What is the veterinary monthly charge?",
    ],
)
def test_unknown_subject_modifier_cannot_borrow_known_insurance_terms(question):
    hits = [hit("Interest and monthly charges apply. Withdrawal charges and death benefits vary.")]
    assert not literal_applicable(question, hits)


def test_unknown_english_modifier_is_not_excused_by_chinese_topic_matches():
    assert not literal_applicable("reinstatement 利息 費用", [hit("利息 費用")])


def test_grammatical_preposition_does_not_require_an_unrelated_source_passage():
    assert literal_applicable(
        "Under this policy, will I pay a withdrawal charge?",
        [hit("A cash withdrawal incurs a withdrawal charge of US$25.")],
    )


@pytest.mark.parametrize(("question", "source"), [
    ("What are the cooling-off rights?", "Cooling-off Period and Right of Cancellation: 21 calendar days."),
    ("Can I withdraw for free at any time?", "Each cash withdrawal is subject to a withdrawal charge of US$25."),
])
def test_ordinary_rights_and_fee_questions_match_the_source_topic(question, source):
    assert literal_applicable(question, [hit(source)])


def test_fee_wording_does_not_excuse_an_unsupported_topic():
    assert not literal_applicable(
        "Can I withdraw for free for veterinary treatment?",
        [hit("Each cash withdrawal is subject to a withdrawal charge of US$25.")],
    )


def test_subject_in_an_unrelated_exclusion_cannot_establish_a_new_fee():
    retriever = StaticRetriever([hit("Interest and withdrawal charge is US$25.")])
    retriever.chunks.append(hit("Reinstatement is mentioned in exclusions.", "other").chunk)
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    answer = asyncio.run(app.answer(ChatRequest(message="What is the reinstatement interest charge?")))
    assert answer.kind == "insufficient" and not answer.citations and not app.llm.calls


@pytest.mark.parametrize(
    "question",
    [
        "What is the reinstatement interest charge?",
        "What is the maternity death benefit?",
        "What is the ransomware withdrawal charge?",
    ],
)
def test_unsupported_modifier_abstains_before_model_or_excerpt_fallback(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "insufficient"
    assert not answer.citations and not app.llm.calls


@pytest.mark.parametrize("question", ["How do I make a claim?", "What happens if I miss a premium payment?"])
def test_ordinary_claim_and_missed_payment_paraphrases_retain_evidence(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer" and answer.citations


@pytest.mark.parametrize(
    "question",
    [
        "How often may I withdraw cash?",
        "How frequently can I withdraw cash?",
        "Can I get my money back if I cancel during the cooling-off period?",
        "What fees apply to a partial withdrawal?",
        "What is the youngest issue age?",
        "How long do surrender charges last?",
        "Can I switch the death benefit option?",
        "Is surrender payment immediate?",
    ],
)
def test_supported_plain_english_questions_keep_their_brochure_evidence(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer" and answer.citations


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


@pytest.mark.parametrize("followup", ["And what about that?", "那是什麼呢？"])
def test_followup_preserves_reviewed_source_conflict(retriever, followup):
    from backend.app.models import ChatTurn

    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(
        app.answer(
            ChatRequest(
                message=followup,
                history=[ChatTurn(
                    role="user",
                    content="What is the minimum increase/decrease amount in sum insured?",
                )],
            )
        )
    )
    assert answer.kind == "insufficient"
    assert len(answer.citations) == 1 and answer.citations[0].page == 17
    assert "conflicting figures" in answer.message
    assert not app.llm.calls


@pytest.mark.parametrize(
    "question",
    [
        "Will I pay a withdrawal charge?",
        "Which charges will I pay when I withdraw money?",
        "Under this policy, will I pay a withdrawal charge?",
    ],
)
def test_policyholder_fee_questions_retain_brochure_evidence(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer"
    assert any("US$25" in citation.excerpt for citation in answer.citations)


@pytest.mark.parametrize(
    "question",
    [
        "Will the insurer pay my claim?",
        "The insurance company will pay my claim, right?",
        "Will this policy pay if I die in an accident?",
    ],
)
def test_insurer_payout_promises_remain_personal_determinations(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "insufficient"
    assert not answer.citations and not app.llm.calls


@pytest.mark.parametrize("question", ["我想了解索償程序。", "我想了解索偿程序。"])
def test_chinese_claims_procedure_is_brochure_education(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer"
    assert any(
        citation.page == 15 and "Claims-Corner" in citation.excerpt
        for citation in answer.citations
    )


@pytest.mark.parametrize("question", ["我可以索償嗎？", "我可以索偿吗？", "我是否受保？", "我一定會獲賠嗎？"])
def test_chinese_personal_claim_determinations_remain_refused(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "insufficient"
    assert not answer.citations and not app.llm.calls


@pytest.mark.parametrize("question", ["冷靜期有多長？", "冷静期有多长？"])
def test_cooling_off_period_matches_both_chinese_scripts(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer"
    assert any(
        citation.page == 15
        and ("21 calendar days" in citation.excerpt or "21個曆日" in citation.excerpt)
        for citation in answer.citations
    )


@pytest.mark.parametrize("question", ["What is the maximum sum insured?", "最高保障額是多少？", "最高保障额是多少？"])
def test_maximum_sum_insured_retains_actual_source_value(retriever, question):
    app = ChatOrchestrator(Settings(_env_file=None), retriever, ScriptedLLM([]))
    app.llm.configured = False
    answer = asyncio.run(app.answer(ChatRequest(message=question)))
    assert answer.kind == "answer"
    assert any(
        citation.page == 17
        and "Maximum Sum Insured" in citation.excerpt
        and "Individual consideration" in citation.excerpt
        and "個別考慮" in citation.excerpt
        for citation in answer.citations
    )
    assert "Individual consideration" in answer.message
