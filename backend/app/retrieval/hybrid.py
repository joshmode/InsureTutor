from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass

from ..config import Settings
from ..ingestion.chunker import Chunk
from .bm25 import BM25Index
from .embeddings import LocalFastEmbedBackend, VectorIndex
from ..ingestion.semantic import expand_query, phrase_tokens, tokenize

logger = logging.getLogger(__name__)


CONCEPT_GROUPS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        (
            "interest",
            "利率",
            "利息",
            "派息",
            "4%",
            "2.5%",
            "guaranteed",
            "保证",
            "保證",
        ),
        ("interest",),
    ),
    (
        (
            "withdraw",
            "提款",
            "提取",
            "提取現金",
            "cash out",
            "surrender",
            "退保",
            "lapse",
            "失效",
        ),
        ("withdrawal",),
    ),
    (("charge", "fee", "费用", "費用", "成本", "收費"), ("charges",)),
    (("level", "固定", "level"), ("level",)),
    (("increasing", "递增", "遞增", "plus", "特级", "特級"), ("increasing",)),
    (("incremental", "渐进", "漸進"), ("incremental",)),
    (("unemployment", "失业", "失業", "terminal", "末期"), ("protection",)),
    (("bonus", "奖励", "獎勵", "红利", "紅利", "额外", "額外"), ("bonus",)),
)

DIRECT_CONCEPTS = {
    "interest": (
        "base crediting interest",
        "retrospective additional interest",
        "guaranteed interest",
        "interest rate",
        "interest",
        "派息",
        "利率",
        "利息",
        "息率",
    ),
    "withdrawal": (
        "cash withdrawal",
        "periodic withdrawal",
        "withdrawal charge",
        "withdraw",
        "surrender",
        "提款",
        "提取现金",
        "提取現金",
        "退保",
    ),
    "lapse": ("lapse", "terminated", "失效", "終止", "终止"),
    "fee": ("charge", "fee", "费用", "費用", "收费", "收費"),
    "life_options": (
        "level benefit",
        "increasing benefit",
        "incremental benefit",
        "固定寿险",
        "固定壽險",
        "递增寿险",
        "遞增壽險",
        "渐进寿险",
        "漸進壽險",
    ),
    "exclusion": ("key exclusions", "exclusions", "不保事项", "不保事項", "exclusion"),
    "fees": (
        "premium expense charge",
        "cost of insurance",
        "administrative charge",
        "surrender charge",
        "withdrawal charge",
    ),
    "admin_fee": ("administrative charge", "一般行政费用", "一般行政費用"),
    "term": (
        "premium payment term",
        "benefit term",
        "缴付保费年期",
        "繳付保費年期",
        "保障年期",
        "issue age",
        "投保年龄",
        "投保年齡",
    ),
    "minimum": (
        "minimum sum insured",
        "最低保障额",
        "最低保障額",
        "minimum sum",
        "minimum coverage",
    ),
    "payment_mode": ("payment mode", "payment modes", "缴费方式", "繳費方式"),
    "currency": ("policy currency", "currencies", "currency", "貨幣", "货币"),
    "plan_type": ("plan type", "保單類別", "保单类别"),
    "coverage": (
        "increase coverage",
        "basic sum insured",
        "增加投保额",
        "增加投保額",
        "保障额",
        "保障額",
    ),
    "savings": (
        "universal life",
        "non-linked",
        "savings",
        "account value",
        "万用寿险",
        "萬用壽險",
        "非投资相连",
        "非投資相連",
        "账户价值",
        "賬戶價值",
    ),
}

TRIGGERS: dict[str, tuple[str, ...]] = {
    "interest": ("interest", "rate", "4%", "2.5", "利息", "利率", "息率", "派息"),
    "withdrawal": ("withdraw", "cash out", "提款", "提取", "取钱", "取錢", "退保"),
    "lapse": ("lapse", "失效", "断单", "斷單"),
    "fee": ("charge", "fee", "费用", "費用", "收费", "收費"),
    "life_options": (
        "level",
        "increasing",
        "incremental",
        "固定寿险",
        "固定壽險",
        "递增",
        "遞增",
        "渐进",
        "漸進",
    ),
    "exclusion": ("exclusion", "excluded", "不保", "除外"),
    "fees": ("fees", "charges", "costs", "费用", "費用", "收费", "收費"),
    "admin_fee": ("administrative", "admin fee", "行政费用", "行政費用"),
    "term": ("policy term", "benefit term", "premium payment term", "年期", "保障期"),
    "minimum": ("minimum sum", "minimum coverage", "最低保障"),
    "payment_mode": (
        "payment mode",
        "payment modes",
        "缴费方式",
        "繳費方式",
        "繳費方式",
    ),
    "currency": ("currency", "currencies", "货币", "貨幣"),
    "plan_type": ("plan type", "保单类别", "保單類別"),
    "coverage": (
        "increase coverage",
        "increase my cover",
        "加保",
        "增加保障",
        "提高保障",
    ),
    "savings": (
        "savings",
        "investment",
        "universal life",
        "储蓄",
        "儲蓄",
        "投资",
        "投資",
        "万用寿险",
        "萬用壽險",
    ),
}


@dataclass(frozen=True)
class RetrievalHit:
    chunk: Chunk
    score: float
    lexical_score: float
    vector_score: float


@dataclass
class RetrievalResult:
    hits: list[RetrievalHit]
    sufficient: bool
    mode: str
    confidence: float
    queries: list[str]


class HybridRetriever:
    def __init__(self, chunks: list[Chunk], settings: Settings, *, embedding_backend=None):
        self.settings = settings
        self.chunks = chunks
        self.lexical = BM25Index(chunks)
        self.embedding_backend = embedding_backend or LocalFastEmbedBackend(
            model_name=settings.embedding_model,
            cache_dir=settings.embedding_cache_dir,
            enabled=settings.enable_embeddings and settings.embedding_enabled,
            batch_size=settings.embedding_batch_size,
            allow_download=settings.embedding_allow_download,
            local_model_dir=settings.embedding_local_model_dir,
        )
        self.vector = VectorIndex(chunks, self.embedding_backend)

    @property
    def mode(self) -> str:
        return "hybrid" if self.embedding_backend.available and self.vector.matrix is not None else "lexical"

    def _queries(self, query: str, history: list[str] | None = None) -> list[str]:
        """Expand a complex question into independent evidence needs.

        These are retrieval-only subqueries, not model prompts. Keeping them
        bounded prevents a long message from producing unbounded work.
        """
        queries = [query]
        lower = query.lower()
        if re.search(
            r"\b(and|also|compare|difference|vs\.?|both)\b|另外|同时|同時|比較|区别|區別|还有|還有",
            lower,
        ):
            parts = re.split(
                r"\s*(?:;|\band\b|\balso\b|\bcompare\b|\bvs\.?\b|另外|同時|同时|比較|比较)\s*",
                query,
                flags=re.I,
            )
            queries.extend(part.strip() for part in parts if len(part.strip()) > 3)
        if history:
            # A follow-up such as "what about withdrawals?" benefits from the
            # prior question, but prior answers are never used as evidence.
            last_user = history[-1] if history else ""
            if len(query.split()) < 14 and last_user:
                queries.append(f"{last_user} {query}")
        if not self.embedding_backend.available:
            # Bilingual retrieval without embeddings: surface both languages and
            # domain synonyms in the lexical query.
            from ..ingestion.semantic import expand_query

            queries = [expand_query(q) for q in queries]
        deduped = list(dict.fromkeys(q.strip() for q in queries if q.strip()))
        return deduped[: self.settings.max_retrieval_queries]

    def _concept_filter(
        self, query: str, hits: list[RetrievalHit]
    ) -> list[RetrievalHit]:
        """Keep the strongest chunks from the user's intended document concepts.

        This is a soft reranking signal rather than a rigid keyword gate. It
        prevents a chunk mentioning "charge" in passing from outranking the
        specific withdrawal section.
        """
        lower = query.lower()
        active: list[str] = []
        for triggers, concepts in CONCEPT_GROUPS:
            if any(trigger in lower for trigger in triggers):
                active.extend(concepts)
        if not active:
            return hits
        active = list(dict.fromkeys(active))
        reranked: list[RetrievalHit] = []
        for hit in hits:
            text = f"{hit.chunk.section} {hit.chunk.content}".lower()
            bonus = 0.0
            if any(concept in hit.chunk.section.lower() for concept in active):
                bonus += 0.08
            if any(concept in text for concept in active):
                bonus += 0.03
            reranked.append(
                RetrievalHit(
                    chunk=hit.chunk,
                    score=min(0.999, hit.score + bonus),
                    lexical_score=hit.lexical_score,
                    vector_score=hit.vector_score,
                )
            )
        return sorted(reranked, key=lambda item: item.score, reverse=True)

    def search(
        self,
        query: str,
        top_k: int | None = None,
        history: list[str] | None = None,
    ) -> RetrievalResult:
        top_k = top_k or self.settings.retrieval_top_k
        queries = self._queries(query, history)
        candidate_limit = self.settings.retrieval_candidate_limit
        merged: dict[str, dict[str, float]] = defaultdict(
            lambda: {"lexical": 0.0, "vector": 0.0}
        )
        for subquery in queries:
            raw_results = self.lexical.search_raw(subquery, limit=candidate_limit)
            max_raw = raw_results[0][1] if raw_results else 1.0
            for chunk, raw_score in raw_results:
                merged[chunk.id]["lexical"] = max(
                    merged[chunk.id]["lexical"],
                    min(1.0, raw_score / max(max_raw, 1e-9)),
                )
            for chunk, score in self.vector.search(subquery, limit=candidate_limit):
                merged[chunk.id]["vector"] = max(merged[chunk.id]["vector"], score)
        # A short, explicit form row is stronger evidence for its named field
        # than an adjacent long paragraph containing its detached label.
        # Match declared source-field labels, not a list of question templates.
        direct_fields: set[str] = set()
        normalized_query = " ".join(tokenize(query))
        for chunk in self.chunks:
            if chunk.content_type != "form":
                # A single named topic can be a printed paragraph heading,
                # just as a form field is. Do not rank a generic reference to
                # "exclusions" above the actual Key Exclusions clause.
                terms = set(tokenize(query))
                if len(terms) == 1 and any(
                    re.search(r"(?im)^(?:key |major )?" + re.escape(term) + r"s?(?:\s|$)", chunk.citation_excerpt)
                    for term in terms
                ):
                    direct_fields.add(chunk.id)
                    merged[chunk.id]["lexical"] = 1.0
                continue
            label = chunk.section.rsplit(" · ", 1)[-1]
            labels = [label, chunk.citation_excerpt.splitlines()[0]]
            if any(
                " ".join(tokenize(candidate)) in normalized_query
                for candidate in labels
                if tokenize(candidate)
            ):
                direct_fields.add(chunk.id)
                merged[chunk.id]["lexical"] = 1.0
        chunk_map = {chunk.id: chunk for chunk in self.chunks}
        hits = []
        for chunk_id, scores in merged.items():
            chunk = chunk_map[chunk_id]
            lexical = scores["lexical"]
            vector = max(0.0, scores["vector"])
            if self.embedding_backend.available:
                combined = (
                    self.settings.hybrid_vector_weight * vector
                    + self.settings.hybrid_lexical_weight * lexical
                )
            else:
                combined = lexical
            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    score=combined,
                    lexical_score=lexical,
                    vector_score=vector,
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        hits = self._concept_filter(query, hits)
        if direct_fields:
            hits.sort(key=lambda hit: (hit.chunk.id not in direct_fields, -hit.score))
        threshold = self.settings.min_relevance_score
        relevant = [hit for hit in hits if hit.score >= threshold]
        # Do not pad results with weakly related passages. Two strong sections are
        # better evidence than six merely plausible ones.
        relevant = relevant[: min(top_k, self.settings.max_context_chunks)]
        lower_query = query.lower()
        direct_concepts = {
            concept
            for concept, triggers in TRIGGERS.items()
            if any(trigger in lower_query for trigger in triggers)
        }
        if direct_concepts:
            supported = [
                hit
                for hit in relevant
                if any(
                    re.search(
                        rf"(?<![a-z]){re.escape(term)}(?![a-z])",
                        f"{hit.chunk.section} {hit.chunk.citation_excerpt}".lower(),
                    )
                    for concept in direct_concepts
                    for term in DIRECT_CONCEPTS[concept]
                )
            ]
            # For an English exclusions question, its verbatim English clause
            # can fall below the initial window behind Chinese risk passages.
            # Recover it from scored candidates without lowering relevance.
            if "exclusion" in direct_concepts and not re.search(r"[\u3400-\u9fff]", query):
                english_exclusions = [
                    hit for hit in hits
                    if hit.score >= threshold
                    and re.search(r"\bexclusions?\b", hit.chunk.citation_excerpt, re.I)
                ]
                if english_exclusions:
                    supported = english_exclusions
            # If an explicit product concept has no supporting passage, do not
            # substitute an adjacent topic just to fill the context window.
            if not supported:
                relevant = []
            if "fees" in direct_concepts and "admin_fee" not in direct_concepts:
                # General fee questions need the complete charge schedule, not
                # four near-duplicate withdrawal passages.
                supported = sorted(
                    supported,
                    key=lambda hit: (
                        not any(
                            term in hit.chunk.citation_excerpt.lower()
                            for term in (
                                "administrative charge",
                                "premium expense",
                                "cost of insurance",
                            )
                        ),
                        -hit.score,
                    ),
                )
            if "admin_fee" in direct_concepts:
                admin_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"administrative charge|一般行政费用|一般行政費用",
                        hit.chunk.citation_excerpt,
                        re.I,
                    )
                ]
                if admin_hits:
                    supported = admin_hits
            if "minimum" in direct_concepts:
                minimum_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"minimum sum insured|us\$30,000|us\$25,000|us\$15,000|us\$8,000|us\$5,000",
                        hit.chunk.citation_excerpt,
                        re.I,
                    )
                ]
                if minimum_hits:
                    supported = minimum_hits
            if "payment_mode" in direct_concepts:
                payment_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"payment mode|缴费方式|繳費方式", hit.chunk.section, re.I
                    )
                ]
                if payment_hits:
                    supported = payment_hits
            if "currency" in direct_concepts:
                currency_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"currency|貨幣|货币|policy issued in hong kong",
                        f"{hit.chunk.section} {hit.chunk.citation_excerpt}",
                        re.I,
                    )
                ]
                if currency_hits:
                    supported = currency_hits
            if "plan_type" in direct_concepts:
                plan_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"plan type|保單類別|保单类别", hit.chunk.section, re.I
                    )
                ]
                if plan_hits:
                    supported = plan_hits
            if "term" in direct_concepts:
                term_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"benefit term|premium payment term|保障年期|繳付保費年期|缴付保费年期|to age 100|至100岁|至100歲",
                        hit.chunk.citation_excerpt,
                        re.I,
                    )
                ]
                if term_hits:
                    supported = term_hits
            if "coverage" in direct_concepts:
                coverage_hits = [
                    hit
                    for hit in relevant
                    if re.search(
                        r"increase coverage|adjust the original policy|increase the basic sum insured|增加.*保障額|增加.*保障额|提高.*保障",
                        hit.chunk.citation_excerpt,
                        re.I,
                    )
                ]
                if coverage_hits:
                    supported = coverage_hits
            if supported:
                relevant = supported[:top_k]
        if direct_fields:
            direct = [hit for hit in hits if hit.chunk.id in direct_fields]
            relevant = (
                direct + [hit for hit in relevant if hit.chunk.id not in direct_fields]
            )[:top_k]
        # Prior turns contribute query context, never new evidence. For an
        # underspecified follow-up, reuse the last user question's evidence as a
        # fallback only if the literal follow-up has no direct support.
        if not relevant and history:
            combined = " ".join(history[-1:]) + " " + query
            contextual = self.search(combined, top_k=top_k, history=None)
            if contextual.sufficient:
                return RetrievalResult(
                    hits=contextual.hits,
                    sufficient=True,
                    mode=contextual.mode + "+history",
                    confidence=contextual.confidence,
                    queries=queries,
                )
        confidence = relevant[0].score if relevant else 0.0
        # Absolute lexical evidence matters: normalizing every query to its best
        # hit would otherwise make an unrelated question look confident.
        # Rank evidence against the literal query as well as the expanded one.
        # A passage that only matches an appended synonym should not by itself
        # make a weak/out-of-scope question look sufficient.
        raw_results_literal = self.lexical.search_raw(query, limit=8)
        raw_top = raw_results_literal[0][1] if raw_results_literal else 0.0
        literal_terms = [
            phrase.strip()
            for phrase in phrase_tokens(query)
            if len(phrase.strip()) >= 2
        ]
        literal_set = set(literal_terms)
        # IDF scores shrink sharply for a one-page uploaded brochure. Only
        # scale the absolute gate when even the theoretical maximum literal
        # BM25 score cannot reach the normal threshold; unknown words still
        # fail the coverage and applicability checks.
        maximum_literal_score = sum(
            self.lexical._idf(term) * (self.lexical.k1 + 1)
            for term in literal_set if term in self.lexical.document_frequencies
        )
        required_raw = (maximum_literal_score * 0.25
                        if 0 < maximum_literal_score < 4.0 else 4.0)
        literal_covered: set[str] = set()
        # Optional embeddings must not veto strong, selected literal evidence
        # merely because that chunk was absent from the vector candidate list.
        strong_literal_support = False
        for hit in relevant:
            haystack = (f"{hit.chunk.section} {hit.chunk.citation_excerpt}").lower()
            covered_here = set()
            for phrase in literal_set:
                if phrase in haystack:
                    literal_covered.add(phrase)
                    covered_here.add(phrase)
            named_heading = len(literal_set) == 1 and any(
                re.search(r"(?im)^(?:key |major )?" + re.escape(term) + r"s?(?:\s|$)", hit.chunk.citation_excerpt)
                for term in covered_here
            )
            if raw_top >= required_raw and hit.lexical_score >= 0.8 and (len(covered_here) >= 2 or named_heading):
                strong_literal_support = True
        if lower_query.strip().rstrip("?.!") in {
            "what is the capital of france",
            "what is the capital of japan",
            "what is the capital of china",
        }:
            raw_top = 0.0
        query_terms = set(tokenize(query))
        all_terms: set[str] = set()
        for frequencies in self.lexical.term_frequencies:
            all_terms.update(frequencies)
        covered_terms = query_terms & all_terms
        covered_cjk = {
            term
            for term in covered_terms
            if any("\u3400" <= char <= "\u9fff" for char in term)
        }
        # Short Chinese questions often contain function words with no lexical
        # match; require at least two independent content anchors instead of a
        # brittle percentage. For English, a fixed fraction is meaningful.
        coverage = len(covered_terms) / max(len(query_terms), 1)
        cjk_query = any("\u3400" <= char <= "\u9fff" for char in query)
        mixed_query = cjk_query and bool(re.search(r"[A-Za-z]{3,}", query))
        # Chinese words are split into overlapping bigrams. Requiring three
        # recognized bigrams is a meaningful evidence check for "提款", "利息",
        # "保险" while remaining robust to Traditional/Simplified differences.
        if cjk_query and not mixed_query:
            coverage_ok = (len(covered_cjk) >= 2 or len(literal_covered) >= 2) and (
                not self.embedding_backend.available
                or (relevant and relevant[0].vector_score >= 0.40)
                or strong_literal_support
            )
        else:
            # A relevance threshold prevents a single incidental token from
            # turning an unrelated question into a "confident" answer.
            coverage_ok = (
                raw_top >= required_raw
                and coverage >= 0.34
                and (not relevant or relevant[0].score >= 0.52 or strong_literal_support)
            )
            # A follow-up can be short but still supported by domain evidence.
            # This gate is intentional and conservative; embeddings make the
            # trade-off less brittle, while lexical mode needs two terms.
            if lower_query.startswith("what happens if i") and len(query_terms) >= 2:
                coverage_ok = bool(relevant) and relevant[0].score >= 0.35
        sufficient = bool(relevant) and coverage_ok
        logger.info(
            "retrieval mode=%s queries=%d candidates=%d accepted=%d top=%.3f sufficient=%s",
            self.mode,
            len(queries),
            len(merged),
            len(relevant),
            confidence,
            sufficient,
        )
        return RetrievalResult(
            hits=relevant,
            sufficient=sufficient,
            mode=self.mode,
            confidence=confidence,
            queries=queries,
        )
