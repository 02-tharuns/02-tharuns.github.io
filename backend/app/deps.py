"""Wires up the singletons every router needs and hangs them off
app.state, built once at startup. FastAPI's `Depends(get_state)` then hands
routers a fully-assembled AppState instead of each router reaching for
globals — this is what makes the mocked-embedder/vector-store tests in
tests/ possible: a test can build its own AppState with fakes and mount the
same routers against it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from .config import Settings, get_settings
from .generation.groq_client import GroqClient
from .guardrails.gates import GuardrailEngine
from .notify import GapDeduper
from .observability.tracer import ObservabilityHub
from .ratelimit import RateLimiter
from .retrieval.bm25 import BM25Index
from .retrieval.embeddings import DeterministicFakeEmbedder, Embedder, FastEmbedEmbedder
from .retrieval.pipeline import RetrievalPipeline
from .retrieval.reranker import FastEmbedReranker, LexicalOverlapReranker, Reranker
from .retrieval.vectorstore import InMemoryVectorStore, QdrantVectorStore, VectorStore
from .textproc import chunk_markdown, compute_bm25_stats

log = logging.getLogger("chappie")


@dataclass
class AppState:
    settings: Settings
    bm25: BM25Index
    pipeline: RetrievalPipeline
    guardrails: GuardrailEngine
    groq: GroqClient
    hub: ObservabilityHub
    rate_limiter: RateLimiter
    gap_deduper: GapDeduper
    report_deduper: GapDeduper


def build_bm25_index(settings: Settings) -> BM25Index:
    corpus_path = Path(settings.bm25_corpus_path)
    if corpus_path.exists():
        return BM25Index.load(corpus_path)

    # No prebuilt corpus.json (fresh checkout, or a test). Build the index
    # in-process from content/*.md so local dev and CI never need to run
    # ingest.py just to boot the server. Real deployments run
    # `python backend/ingest.py` first so this path is unused there.
    content_dir = Path(settings.content_dir)
    if not content_dir.exists():
        raise RuntimeError(
            f"No BM25 corpus at {corpus_path} and no content/ at {content_dir} to build one from. "
            "Run `python backend/ingest.py` first."
        )
    chunks = []
    for path in sorted(content_dir.glob("*.md")):
        chunks.extend(chunk_markdown(path.stem, path.read_text()))
    df, avgdl = compute_bm25_stats(chunks)
    return BM25Index(chunks=chunks, df=df, avgdl=avgdl)


def build_embedder_and_store(settings: Settings) -> tuple[Embedder | None, VectorStore | None]:
    if not settings.use_dense:
        return None, None
    try:
        embedder: Embedder = FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim)
        if settings.qdrant_url:
            store: VectorStore = QdrantVectorStore(
                settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection, settings.embedding_dim
            )
        else:
            log.warning("QDRANT_URL not set — falling back to an in-memory vector store (dense recall is process-local and empty until ingest.py populates it in-process).")
            store = InMemoryVectorStore(settings.embedding_dim)
        return embedder, store
    except Exception:  # noqa: BLE001 — dense retrieval is an enhancement, not a requirement
        log.exception("Failed to initialise dense retrieval; continuing BM25-only.")
        return None, None


def build_reranker(settings: Settings) -> Reranker:
    if not settings.use_reranker:
        return LexicalOverlapReranker()
    try:
        return FastEmbedReranker(settings.reranker_model)
    except Exception:  # noqa: BLE001
        log.exception("Failed to initialise cross-encoder reranker; falling back to lexical overlap.")
        return LexicalOverlapReranker()


def build_app_state(settings: Settings | None = None) -> AppState:
    settings = settings or get_settings()
    bm25 = build_bm25_index(settings)
    embedder, vector_store = build_embedder_and_store(settings)
    reranker = build_reranker(settings)

    pipeline = RetrievalPipeline(
        bm25=bm25, embedder=embedder, vector_store=vector_store, reranker=reranker,
        rrf_k=settings.rrf_k, bm25_top_n=settings.bm25_top_n, dense_top_n=settings.dense_top_n,
        fusion_top_n=settings.fusion_top_n, use_dense=settings.use_dense, use_reranker=settings.use_reranker,
    )
    guardrails = GuardrailEngine(
        bm25=bm25, pipeline=pipeline, owner=settings.owner_name, contact_email=settings.contact_email,
    )
    groq = GroqClient(settings.groq_api_key, settings.groq_url, settings.groq_model)
    hub = ObservabilityHub(settings.db_path, ring_buffer_size=settings.trace_ring_buffer)
    rate_limiter = RateLimiter(settings)
    gap_deduper = GapDeduper()
    report_deduper = GapDeduper()

    return AppState(
        settings=settings, bm25=bm25, pipeline=pipeline, guardrails=guardrails,
        groq=groq, hub=hub, rate_limiter=rate_limiter, gap_deduper=gap_deduper,
        report_deduper=report_deduper,
    )


def get_state(request: Request) -> AppState:
    return request.app.state.chappie
