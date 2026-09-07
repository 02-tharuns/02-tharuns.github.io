"""Orchestrates hybrid retrieval: BM25 candidates + dense candidates -> RRF
fusion -> cross-encoder rerank -> confidence scoring for the evidence gate.

Why BM25 stays the confidence signal
-------------------------------------
guardrails/gates.py's evidenceFloor (0.34) and scopeCoverageFloor/scopeScoreFloor
were calibrated against the browser's pure-BM25 0..1 confidence score across a
97-case eval suite. Cross-encoder logits and cosine similarities live on
different, uncalibrated scales — swapping the gate's input out from under it
would silently invalidate every threshold the eval suite checks. So: dense
retrieval and RRF fusion widen the CANDIDATE set (catching semantic matches
BM25's lexical scoring misses), the reranker decides the FINAL ORDER among
those candidates, and BM25Index.score_confidence() computes the number the
gates actually compare against a threshold — for whichever chunks ended up
selected, not just the ones BM25 itself would have surfaced.

Degrading gracefully
---------------------
Qdrant Cloud or the embedding/reranker models being unreachable must not take
the whole bot down — extractive BM25-only answering is the original product
and it worked. `retrieve()` catches retrieval-stage failures per-stage and
falls back to the next thing down, recording what happened in the trace.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..textproc import Chunk, expand, tokenise
from .bm25 import BM25Index
from .embeddings import Embedder
from .fusion import fuse_ranked
from .reranker import LexicalOverlapReranker, Reranker, rerank_chunks
from .vectorstore import VectorStore


@dataclass
class Hit:
    chunk: Chunk
    score: float          # 0..1, BM25-calibrated confidence — what gates compare
    bm25_raw: float = 0.0
    dense_score: float | None = None
    rerank_score: float | None = None
    source: str = "bm25"  # "bm25" | "dense" | "both"


class RetrievalPipeline:
    def __init__(
        self,
        bm25: BM25Index,
        embedder: Embedder | None,
        vector_store: VectorStore | None,
        reranker: Reranker | None,
        rrf_k: int = 60,
        bm25_top_n: int = 12,
        dense_top_n: int = 12,
        fusion_top_n: int = 8,
        use_dense: bool = True,
        use_reranker: bool = True,
    ):
        self.bm25 = bm25
        self.embedder = embedder
        self.vector_store = vector_store
        self.reranker = reranker or LexicalOverlapReranker()
        self.rrf_k = rrf_k
        self.bm25_top_n = bm25_top_n
        self.dense_top_n = dense_top_n
        self.fusion_top_n = fusion_top_n
        self.use_dense = use_dense and embedder is not None and vector_store is not None
        self.use_reranker = use_reranker

    def retrieve(self, raw_text: str, trace=None) -> tuple[list[Hit], list[str], list[str]]:
        """Returns (hits, tokens, expanded_terms). `trace`, if given, is an
        observability.tracer.Trace — each stage is recorded as one span."""
        _span = trace.span if trace else _noop_span

        with _span("tokenise") as rec:
            tokens = tokenise(raw_text)
            terms = expand(tokens, raw_text)
            if trace:
                rec["meta"] = {"tokens": tokens, "expanded_terms": terms}

        with _span("retrieve_bm25") as rec:
            bm25_hits = self.bm25.retrieve(terms, candidates=self.bm25_top_n)
            bm25_ids = [h.chunk.id for h in bm25_hits]
            if trace:
                rec["meta"] = {"candidates": len(bm25_hits), "top": bm25_ids[:5]}

        dense_ids: list[str] = []
        dense_scores: dict[str, float] = {}
        if self.use_dense:
            with _span("retrieve_dense") as rec:
                try:
                    term_set = {t for t in terms}
                    query_vec = self.embedder.encode([raw_text])[0]
                    raw_results = self.vector_store.search(query_vec, top_n=self.dense_top_n)
                    for chunk_id, sim in raw_results:
                        chunk = self.bm25.chunks_by_id.get(chunk_id)
                        if chunk and self.bm25.eligible(chunk, term_set):
                            dense_ids.append(chunk_id)
                            dense_scores[chunk_id] = sim
                    if trace:
                        rec["meta"] = {"candidates": len(dense_ids), "top": dense_ids[:5]}
                except Exception as exc:  # noqa: BLE001 — degrade, never 500 the whole ask
                    if trace:
                        rec["meta"] = {"error": str(exc)}
                    dense_ids = []

        with _span("fuse_rrf") as rec:
            if dense_ids:
                fused_ids = fuse_ranked([bm25_ids, dense_ids], k=self.rrf_k, top_n=self.fusion_top_n)
            else:
                fused_ids = bm25_ids[: self.fusion_top_n]
            fused_chunks = [self.bm25.chunks_by_id[i] for i in fused_ids if i in self.bm25.chunks_by_id]
            if trace:
                rec["meta"] = {"fused": fused_ids}

        if self.use_reranker and len(fused_chunks) > 1:
            with _span("rerank") as rec:
                try:
                    ranked = rerank_chunks(self.reranker, raw_text, fused_chunks)
                    fused_chunks = [c for c, _ in ranked]
                    rerank_scores = {c.id: s for c, s in ranked}
                    if trace:
                        rec["meta"] = {"order": [c.id for c in fused_chunks]}
                except Exception as exc:  # noqa: BLE001
                    rerank_scores = {}
                    if trace:
                        rec["meta"] = {"error": str(exc)}
        else:
            rerank_scores = {}

        with _span("score_confidence") as rec:
            bm25_raw_by_id = {h.chunk.id: h.raw for h in bm25_hits}
            ceiling = max([h.raw for h in bm25_hits] + [6.0])
            seen_docs: dict[str, int] = {}
            hits: list[Hit] = []
            for chunk in fused_chunks:
                seen_docs[chunk.doc] = seen_docs.get(chunk.doc, 0) + 1
                rank_in_doc = seen_docs[chunk.doc]
                raw = bm25_raw_by_id.get(chunk.id) or self.bm25.score(chunk, terms)
                confidence = self.bm25.score_confidence(chunk, terms, ceiling, rank_in_doc) if chunk.id not in bm25_raw_by_id \
                    else min(raw * (self.bm25.same_doc_penalty ** (rank_in_doc - 1)) / ceiling, 1.0)
                source = "both" if chunk.id in dense_scores and chunk.id in bm25_raw_by_id else (
                    "dense" if chunk.id in dense_scores else "bm25"
                )
                hits.append(Hit(
                    chunk=chunk, score=confidence, bm25_raw=raw,
                    dense_score=dense_scores.get(chunk.id), rerank_score=rerank_scores.get(chunk.id),
                    source=source,
                ))
            hits.sort(key=lambda h: h.score, reverse=True)
            if trace:
                rec["meta"] = {"scores": {h.chunk.id: round(h.score, 3) for h in hits}}

        return hits, tokens, terms


class _NoopSpanCtx:
    def __enter__(self):
        return {}

    def __exit__(self, *exc):
        return False


def _noop_span(name: str, **meta):
    return _NoopSpanCtx()
