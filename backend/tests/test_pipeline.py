"""RetrievalPipeline end-to-end against the real content/ corpus, with the
deterministic fake embedder + in-memory vector store + lexical-overlap
reranker standing in for Qdrant/fastembed (unreachable from this sandbox).
The point of these tests is the PLUMBING — eligibility filtering survives
fusion, dense-retrieval failure degrades gracefully, scores stay 0..1 — not
retrieval quality, which the fake embedder can't meaningfully represent.
"""


def test_retrieve_returns_hits_on_the_scale_gates_expect(state):
    hits, tokens, terms = state.pipeline.retrieve("Tell me about DARE-PM")
    assert hits
    assert all(0.0 <= h.score <= 1.0 for h in hits)
    assert tokens and terms


def test_retrieve_degrades_gracefully_when_dense_retrieval_throws(state, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("qdrant unreachable")

    monkeypatch.setattr(state.pipeline.vector_store, "search", boom)
    hits, _, _ = state.pipeline.retrieve("Tell me about DARE-PM")
    assert hits  # BM25 alone still answers


def test_retrieve_respects_gated_chunk_eligibility(state):
    gated = [c for c in state.bm25.chunks if not c.volunteer]
    if not gated:
        return
    chunk = gated[0]
    # A query with none of the gated chunk's terms/triggers should not
    # surface it even via dense retrieval fusion.
    hits, _, _ = state.pipeline.retrieve("completely unrelated filler text about nothing")
    assert chunk.id not in {h.chunk.id for h in hits}


def test_trace_records_spans(state):
    from app.observability.tracer import Trace

    trace = Trace(question="Tell me about DARE-PM")
    hits, _, _ = state.pipeline.retrieve("Tell me about DARE-PM", trace=trace)
    names = {s["name"] for s in trace.spans}
    assert "tokenise" in names
    assert "retrieve_bm25" in names
    assert "fuse_rrf" in names
    assert "score_confidence" in names
