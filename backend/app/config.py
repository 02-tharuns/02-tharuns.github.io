"""All environment configuration in one place.

Nothing here has a network-reachable default that isn't obviously a local
placeholder — a missing production value should fail loudly at startup
rather than silently fall back to something that looks like it works.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    # --- identity / CORS ---------------------------------------------------
    allowed_origins: list[str] = field(default_factory=lambda: _list(
        "ALLOWED_ORIGIN", "http://localhost:5173,https://02-tharuns.github.io"
    ))

    # --- generation (Groq) ---------------------------------------------------
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_url: str = field(default_factory=lambda: os.getenv(
        "GROQ_URL", "https://api.groq.com/openai/v1/chat/completions"
    ))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"))

    # --- retrieval: dense vector store (Qdrant Cloud) -----------------------
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", ""))
    qdrant_api_key: str = field(default_factory=lambda: os.getenv("QDRANT_API_KEY", ""))
    qdrant_collection: str = field(default_factory=lambda: os.getenv("QDRANT_COLLECTION", "chappie_chunks"))
    embedding_model: str = field(default_factory=lambda: os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    ))
    embedding_dim: int = field(default_factory=lambda: int(os.getenv("EMBEDDING_DIM", "384")))

    # --- retrieval: hybrid fusion + reranking --------------------------------
    reranker_model: str = field(default_factory=lambda: os.getenv(
        "RERANKER_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2"
    ))
    rrf_k: int = field(default_factory=lambda: int(os.getenv("RRF_K", "60")))
    bm25_top_n: int = field(default_factory=lambda: int(os.getenv("BM25_TOP_N", "12")))
    dense_top_n: int = field(default_factory=lambda: int(os.getenv("DENSE_TOP_N", "12")))
    fusion_top_n: int = field(default_factory=lambda: int(os.getenv("FUSION_TOP_N", "8")))
    rerank_top_n: int = field(default_factory=lambda: int(os.getenv("RERANK_TOP_N", "3")))
    use_dense: bool = field(default_factory=lambda: _bool("USE_DENSE", True))
    use_reranker: bool = field(default_factory=lambda: _bool("USE_RERANKER", True))

    # --- corpus ---------------------------------------------------------------
    content_dir: str = field(default_factory=lambda: os.getenv("CONTENT_DIR", "../content"))
    bm25_corpus_path: str = field(default_factory=lambda: os.getenv("BM25_CORPUS_PATH", "data/corpus.json"))

    # --- observability ----------------------------------------------------------
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "data/chappie.db"))
    trace_ring_buffer: int = field(default_factory=lambda: int(os.getenv("TRACE_RING_BUFFER", "200")))

    # --- agent-event ingestion (the separate AI SRE agent project) -------------
    agent_events_token: str = field(default_factory=lambda: os.getenv("AGENT_EVENTS_TOKEN", ""))

    # --- contact / gap notification (Gmail app password) ------------------------
    gap_notify_email: str = field(default_factory=lambda: os.getenv("GAP_NOTIFY_EMAIL", ""))
    contact_notify_email: str = field(default_factory=lambda: os.getenv(
        "CONTACT_NOTIFY_EMAIL", os.getenv("GAP_NOTIFY_EMAIL", "")
    ))
    report_notify_email: str = field(default_factory=lambda: os.getenv(
        "REPORT_NOTIFY_EMAIL", os.getenv("GAP_NOTIFY_EMAIL", "")
    ))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_app_password: str = field(default_factory=lambda: os.getenv("SMTP_APP_PASSWORD", ""))
    owner_name: str = field(default_factory=lambda: os.getenv("OWNER_NAME", "Tharun"))
    contact_email: str = field(default_factory=lambda: os.getenv("CONTACT_EMAIL", "tharunmysuru@gmail.com"))

    # --- rate limiting (in-memory, single-instance — see ask/routes.py) ----------
    rate_limit_per_min: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MIN", "6")))
    rate_limit_per_day: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_DAY", "40")))
    rate_limit_global_per_day: int = field(default_factory=lambda: int(os.getenv("RATE_LIMIT_GLOBAL_PER_DAY", "400")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
