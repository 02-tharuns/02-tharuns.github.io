"""FastAPI app factory. `uvicorn app.main:app` runs the module-level `app`
in production; the test suite calls `create_app(state=fake_state)` directly
so tests never touch Qdrant Cloud, Groq, or a real embedding model download.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agents.routes import router as agents_router
from .ask.routes import router as ask_router
from .config import get_settings
from .contact.routes import router as contact_router
from .deps import AppState, build_app_state
from .evals.routes import router as evals_router
from .observability.routes import router as observability_router
from .report.routes import router as report_router

logging.basicConfig(level=logging.INFO)


def create_app(state: AppState | None = None) -> FastAPI:
    """Builds the ASGI app. When `state` is given (tests, or any embedder),
    startup uses it as-is instead of constructing a fresh one from the
    environment — real Qdrant/Groq/model calls never happen in that path."""
    settings = state.settings if state else get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # A slow model/index load happens here, after the ASGI app object
        # exists, so `uvicorn app.main:app` can import this module fast and
        # only pay the load cost once the server actually starts serving.
        app.state.chappie = state or build_app_state(settings)
        yield

    app = FastAPI(title="Chappie", version="2.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )

    app.include_router(ask_router)
    app.include_router(contact_router)
    app.include_router(report_router)
    app.include_router(agents_router)
    app.include_router(observability_router)
    app.include_router(evals_router)

    return app


app = create_app()
