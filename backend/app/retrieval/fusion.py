"""Reciprocal Rank Fusion — combines the BM25 (lexical) and Qdrant (dense)
rankings into one candidate list without needing their scores to be on
comparable scales, which they never are (BM25 raw scores are unbounded and
corpus-size-dependent; cosine similarity is bounded -1..1)."""

from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[str]],
    k: int = 60,
    weights: list[float] | None = None,
) -> dict[str, float]:
    """Each inner list is an ordered (best-first) list of chunk ids from one
    retriever. Returns {id: fused_score}, higher is better. `weights`, if
    given, scales each retriever's contribution (e.g. to favour lexical
    matches while dense retrieval is still cheap/experimental)."""
    weights = weights or [1.0] * len(ranked_id_lists)
    scores: dict[str, float] = {}
    for ranked_ids, weight in zip(ranked_id_lists, weights):
        for rank, doc_id in enumerate(ranked_ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * (1.0 / (k + rank))
    return scores


def fuse_ranked(
    ranked_id_lists: list[list[str]],
    k: int = 60,
    top_n: int | None = None,
    weights: list[float] | None = None,
) -> list[str]:
    """Convenience wrapper: returns the fused, sorted id list (best first)."""
    scores = reciprocal_rank_fusion(ranked_id_lists, k=k, weights=weights)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    ids = [doc_id for doc_id, _ in ordered]
    return ids[:top_n] if top_n else ids
