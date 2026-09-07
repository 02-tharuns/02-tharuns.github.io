"""Hybrid retrieval: BM25 (lexical) + Qdrant dense (semantic), fused with
Reciprocal Rank Fusion, reordered by a cross-encoder reranker.

BM25 stays the confidence signal the guardrail gates were calibrated against
(evidenceFloor / scopeCoverageFloor in guardrails/gates.py) — dense retrieval
and reranking change *which* chunks are selected and in what order, not the
score gates compare against a threshold. See pipeline.py's module docstring
for the full reasoning.
"""
