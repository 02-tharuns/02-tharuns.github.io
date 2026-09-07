"""GET endpoints backing the frontend's evals dashboard, plus the ingestion
endpoint the Python eval harness (evals/run_evals.py) posts a finished run
to. Read-heavy, write-once-per-CI-run — this is history, not a live feed."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from ..deps import AppState, get_state
from ..schemas import EvalRunDetail, EvalRunSummary

router = APIRouter()


@router.get("/evals/runs", response_model=list[EvalRunSummary])
def list_runs(limit: int = 50, state: AppState = Depends(get_state)):
    limit = max(1, min(limit, 200))
    return state.hub.store.list_eval_runs(limit=limit)


@router.get("/evals/runs/{run_id}", response_model=EvalRunDetail)
def get_run(run_id: str, state: AppState = Depends(get_state)):
    run = state.hub.store.get_eval_run(run_id)
    if not run:
        raise HTTPException(404, "Eval run not found.")
    return run


@router.post("/evals/runs", response_model=EvalRunDetail)
def ingest_run(run: EvalRunDetail, authorization: str | None = Header(default=None), state: AppState = Depends(get_state)):
    # Reuses the same bearer token as agent-event ingestion — both are
    # "a trusted CI job posts results here", not a visitor-facing surface.
    expected = state.settings.agent_events_token
    if not expected or authorization != f"Bearer {expected}":
        raise HTTPException(401, "Invalid or missing bearer token.")
    state.hub.store.insert_eval_run(run.model_dump())
    return run
