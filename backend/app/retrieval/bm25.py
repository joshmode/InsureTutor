from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from ..ingestion.chunker import Chunk
from ..ingestion.semantic import expand_query, normalize_term, tokenize


@dataclass
class LexicalResult:
    chunk: Chunk
    score: float


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.docs = [
            tokenize(c.content)
            + tokenize(c.section) * 2
            + tokenize(c.document)
            for c in chunks
        ]
        self.doc_lengths = [len(doc) for doc in self.docs]
        self.avg_length = sum(self.doc_lengths) / max(len(self.doc_lengths), 1)
        self.term_frequencies = [Counter(doc) for doc in self.docs]
        self.document_frequencies: Counter[str] = Counter()
        for frequencies in self.term_frequencies:
            self.document_frequencies.update(frequencies.keys())
        self.n_docs = len(chunks)

    def _idf(self, term: str) -> float:
        df = self.document_frequencies.get(term, 0)
        return math.log(1 + (self.n_docs - df + 0.5) / (df + 0.5))

    def search(self, query: str, limit: int = 16) -> list[LexicalResult]:
        query_tokens = tokenize(normalize_term(expand_query(query)))
        if not query_tokens:
            return []
        unique_terms = list(dict.fromkeys(query_tokens))
        scored: list[LexicalResult] = []
        for index, frequencies in enumerate(self.term_frequencies):
            length = self.doc_lengths[index]
            score = 0.0
            for term in unique_terms:
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * length / max(self.avg_length, 1)
                )
                score += self._idf(term) * (tf * (self.k1 + 1)) / denominator
            if score > 0:
                scored.append(LexicalResult(chunk=self.chunks[index], score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        if not scored:
            return []
        max_score = max(item.score for item in scored)
        return [
            LexicalResult(chunk=item.chunk, score=item.score / max_score)
            for item in scored[:limit]
        ]

    def best_raw_score(self, query: str) -> float:
        query_tokens = tokenize(normalize_term(expand_query(query)))
        if not query_tokens:
            return 0.0
        scores = self.search(query, limit=1)
        if not scores:
            return 0.0
        # Recompute unnormalized best score for diagnostics and confidence.
        return max(
            (
                sum(
                    self._idf(term)
                    * (frequencies.get(term, 0) * (self.k1 + 1))
                    / (
                        frequencies.get(term, 0)
                        + self.k1
                        * (
                            1
                            - self.b
                            + self.b * length / max(self.avg_length, 1)
                        )
                    )
                    for term in dict.fromkeys(query_tokens)
                    if frequencies.get(term, 0)
                )
                for index, frequencies in enumerate(self.term_frequencies)
                for length in [self.doc_lengths[index]]
            ),
            default=0.0,
        )

    def search_raw(self, query: str, limit: int = 16) -> list[tuple[Chunk, float]]:
        query_tokens = tokenize(expand_query(query))
        if not query_tokens:
            return []
        unique_terms = list(dict.fromkeys(query_tokens))
        scored: list[tuple[Chunk, float]] = []
        for index, frequencies in enumerate(self.term_frequencies):
            length = self.doc_lengths[index]
            score = 0.0
            for term in unique_terms:
                tf = frequencies.get(term, 0)
                if not tf:
                    continue
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * length / max(self.avg_length, 1)
                )
                score += self._idf(term) * (tf * (self.k1 + 1)) / denominator
            if score > 0:
                scored.append((self.chunks[index], score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:limit]

