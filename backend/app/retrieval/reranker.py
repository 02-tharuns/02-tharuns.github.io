"""Cross-encoder reranking stage — fastembed's ONNX TextCrossEncoder, for
the same memory-budget reason as embeddings.py's choice of fastembed over
sentence-transformers: no torch, tens of MB instead of hundreds, fits a
Render free-tier instance running the whole service.

BM25 and dense retrieval both score query and document independently
(bi-encoder style) — fast, but blind to interactions between the two texts.
A cross-encoder scores the (query, passage) pair jointly, which is slower
(so it only runs on the small fused candidate set, not the whole corpus)
but noticeably better at picking the single most relevant passage out of
several plausible ones — exactly the job that matters right before the
evidence gate decides whether to answer at all.
"""

from __future__ import annotations

from typing import Protocol

from ..textproc import Chunk


class Reranker(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class FastEmbedReranker:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self._model = TextCrossEncoder(model_name=self.model_name)
        return self._model

    def score(self, query: str, passages: list[str]) -> list[float]:
        model = self._load()
        return [float(s) for s in model.rerank(query, passages)]


class LexicalOverlapReranker:
    """Fallback/test reranker with no model download: scores each passage by
    stemmed token overlap with the query. Used when USE_RERANKER=false, when
    the real model can't be loaded (sandboxed dev, offline tests), or as the
    pipeline's degrade-gracefully path if model loading fails at request
    time — a worse ranking signal is better than a 500 on every question."""

    def score(self, query: str, passages: list[str]) -> list[float]:
        from ..textproc import tokenise
        q = set(tokenise(query))
        out = []
        for passage in passages:
            terms = tokenise(passage)
            if not terms:
                out.append(0.0)
                continue
            overlap = sum(1 for t in terms if t in q)
            out.append(overlap / len(terms))
        return out


def rerank_chunks(reranker: Reranker, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
    if not chunks:
        return []
    scores = reranker.score(query, [c.text for c in chunks])
    paired = list(zip(chunks, scores))
    paired.sort(key=lambda cs: cs[1], reverse=True)
    return paired
