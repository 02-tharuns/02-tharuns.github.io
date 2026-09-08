"""Shared fixtures.

Everything network-dependent (Qdrant Cloud, Groq, real embedding/reranker
model downloads) is replaced with a fake here — this sandbox has no route to
any of those hosts, and even where it does (CI, production) unit tests
should never depend on a third party being up. See app/retrieval/embeddings.py
and reranker.py for the fakes' own docstrings.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings  # noqa: E402
from app.deps import AppState, build_bm25_index  # noqa: E402
from app.guardrails.gates import GuardrailEngine  # noqa: E402
from app.notify import GapDeduper  # noqa: E402
from app.observability.tracer import ObservabilityHub  # noqa: E402
from app.ratelimit import RateLimiter  # noqa: E402
from app.retrieval.embeddings import DeterministicFakeEmbedder  # noqa: E402
from app.retrieval.pipeline import RetrievalPipeline  # noqa: E402
from app.retrieval.reranker import LexicalOverlapReranker  # noqa: E402
from app.retrieval.vectorstore import InMemoryVectorStore  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT_DIR = REPO_ROOT / "content"


class FakeGroqClient:
    """Swaps in for GroqClient in tests. `next_answer` controls what
    complete()/stream() produce; set it to a GroqError instance to simulate
    an upstream failure and exercise the extractive fallback path."""

    def __init__(self, next_answer: str = "NO_EVIDENCE"):
        self.next_answer = next_answer
        self.calls: list[list[dict]] = []

    async def complete(self, messages, temperature=0.2, max_tokens=500):
        self.calls.append(messages)
        if isinstance(self.next_answer, Exception):
            raise self.next_answer
        # Fixed fake usage so token-cost-tracking has something deterministic
        # to assert against, without this test depending on real Groq output.
        return self.next_answer, {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}

    async def stream(self, messages, temperature=0.2, max_tokens=500, usage_sink: dict | None = None):
        self.calls.append(messages)
        if isinstance(self.next_answer, Exception):
            raise self.next_answer
        for word in self.next_answer.split(" "):
            yield word + " "
        if usage_sink is not None:
            usage_sink.update({"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120})


def make_settings(tmp_path, **overrides) -> Settings:
    defaults = dict(
        content_dir=str(CONTENT_DIR),
        bm25_corpus_path=str(tmp_path / "corpus.json"),
        db_path=str(tmp_path / "chappie.db"),
        use_dense=True,
        use_reranker=True,
        agent_events_token="test-token",
        # Non-empty so ask/routes.py's `if not groq_api_key: skip straight to
        # extractive` branch doesn't short-circuit before FakeGroqClient ever
        # gets called — this is a fake key, FakeGroqClient never makes a real
        # network call regardless.
        groq_api_key="test-key",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def make_state(tmp_path, groq_answer: str = "NO_EVIDENCE", **settings_overrides) -> AppState:
    settings = make_settings(tmp_path, **settings_overrides)
    bm25 = build_bm25_index(settings)
    embedder = DeterministicFakeEmbedder(dim=32)
    vector_store = InMemoryVectorStore(dim=32)
    # Populate the fake dense index with every chunk so dense retrieval has
    # something to search — the hash embedder isn't semantically meaningful,
    # but this at least exercises the fusion/rerank plumbing end-to-end.
    texts = [f"{c.heading}. {c.text}" for c in bm25.chunks]
    vectors = embedder.encode(texts)
    vector_store.upsert([c.id for c in bm25.chunks], vectors, [{} for _ in bm25.chunks])

    pipeline = RetrievalPipeline(
        bm25=bm25, embedder=embedder, vector_store=vector_store, reranker=LexicalOverlapReranker(),
        rrf_k=60, bm25_top_n=12, dense_top_n=12, fusion_top_n=8, use_dense=True, use_reranker=True,
    )
    guardrails = GuardrailEngine(bm25=bm25, pipeline=pipeline, owner=settings.owner_name, contact_email=settings.contact_email)
    hub = ObservabilityHub(settings.db_path)
    return AppState(
        settings=settings, bm25=bm25, pipeline=pipeline, guardrails=guardrails,
        groq=FakeGroqClient(groq_answer), hub=hub, rate_limiter=RateLimiter(settings), gap_deduper=GapDeduper(),
        report_deduper=GapDeduper(),
    )


@pytest.fixture
def state(tmp_path):
    return make_state(tmp_path)


@pytest.fixture
def app_client(tmp_path):
    from fastapi.testclient import TestClient

    from app.main import create_app

    s = make_state(tmp_path)
    app = create_app(state=s)
    with TestClient(app) as client:
        client.state = s  # convenient access to swap client.state.groq.next_answer mid-test
        yield client
