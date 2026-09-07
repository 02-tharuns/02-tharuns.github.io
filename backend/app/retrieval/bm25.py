"""Okapi BM25 over the prebuilt index — the same math as assets/chatbot.js,
now running server-side. Ported field-for-field so the two stay comparable."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from ..textproc import Chunk


@dataclass
class BM25Hit:
    chunk: Chunk
    raw: float   # unnormalised BM25 score
    score: float  # 0..1 confidence, same-doc damped, ceiling-normalised


class BM25Index:
    def __init__(self, chunks: list[Chunk], df: dict[str, int], avgdl: float,
                 k1: float = 1.5, b: float = 0.75, same_doc_penalty: float = 0.72):
        self.chunks = chunks
        self.chunks_by_id = {c.id: c for c in chunks}
        self.df = df
        self.n = len(chunks)
        self.avgdl = avgdl or 1.0
        self.k1 = k1
        self.b = b
        self.same_doc_penalty = same_doc_penalty
        self.vocab = set(df.keys())

    @classmethod
    def load(cls, path: str | Path) -> "BM25Index":
        data = json.loads(Path(path).read_text())
        chunks = [Chunk.from_dict(c) for c in data["chunks"]]
        return cls(chunks=chunks, df=data["df"], avgdl=data["avgdl"])

    def save(self, path: str | Path) -> None:
        document_frequency = self.df
        payload = {
            "version": 2,
            "N": self.n,
            "avgdl": self.avgdl,
            "df": dict(sorted(document_frequency.items())),
            "chunks": [c.to_dict() for c in self.chunks],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(payload, ensure_ascii=False))

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.n - n + 0.5) / (n + 0.5))

    def score(self, chunk: Chunk, terms: list[str]) -> float:
        total = 0.0
        for term in terms:
            f = chunk.tf.get(term)
            if not f:
                continue
            denominator = f + self.k1 * (1 - self.b + self.b * (chunk.len / self.avgdl))
            total += self.idf(term) * (f * (self.k1 + 1)) / denominator
        return total

    def eligible(self, chunk: Chunk, term_set: set[str]) -> bool:
        """A gated chunk (volunteer: false) is invisible unless the query names
        one of its trigger terms — stops a niche passage bleeding into every
        answer (e.g. a contact question surfacing unrelated content)."""
        if chunk.volunteer:
            return True
        return any(t in term_set for t in chunk.triggers)

    def retrieve(self, terms: list[str], candidates: int = 12) -> list[BM25Hit]:
        unique = list(dict.fromkeys(terms))
        term_set = set(unique)
        scored = [
            (chunk, self.score(chunk, unique))
            for chunk in self.chunks
            if self.eligible(chunk, term_set)
        ]
        scored = [(c, s) for c, s in scored if s > 0]
        scored.sort(key=lambda cs: cs[1], reverse=True)
        scored = scored[:candidates]
        if not scored:
            return []

        ceiling = max(scored[0][1], 6)
        seen: dict[str, int] = {}
        hits = []
        for chunk, raw in scored:
            seen[chunk.doc] = seen.get(chunk.doc, 0) + 1
            rank = seen[chunk.doc]
            damped = raw * (self.same_doc_penalty ** (rank - 1))
            hits.append(BM25Hit(chunk=chunk, raw=raw, score=min(damped / ceiling, 1.0)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def score_confidence(self, chunk: Chunk, terms: list[str], ceiling: float, rank_in_doc: int) -> float:
        """Score an arbitrary chunk (e.g. one that surfaced only via dense
        retrieval) on the same 0..1 scale `retrieve()` uses, so hybrid results
        remain comparable against the calibrated evidence/scope floors."""
        raw = self.score(chunk, terms)
        damped = raw * (self.same_doc_penalty ** (rank_in_doc - 1))
        return min(damped / ceiling, 1.0) if ceiling > 0 else 0.0
