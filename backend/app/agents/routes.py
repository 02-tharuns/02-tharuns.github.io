"""Generic ingestion endpoint for the separate AI SRE agent project.

That project is its own codebase with its own release cadence — this
endpoint's contract is deliberately thin (agent name, event kind, severity,
free-form message + payload) so it never needs to change in lockstep with
whatever the SRE agent decides to observe next. This service's job is to
store what it's told and let the frontend's observability dashboard render
it next to the RAG pipeline's own traces, not to interpret it.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..deps import AppState, get_state
from ..schemas import AgentEvent, AgentEventOut

router = APIRouter()


def _check_token(state: AppState, authorization: str | None) -> None:
    expected = state.settings.agent_events_token
    if not expected:
        # No token configured means the operator hasn't set one up yet.
        # Refuse rather than silently accepting unauthenticated writes from
        # whoever finds the URL.
        raise HTTPException(503, "Agent event ingestion is not configured.")
    if authorization != f"Bearer {expected}":
        raise HTTPException(401, "Invalid or missing bearer token.")


@router.post("/agents/events", response_model=AgentEventOut)
async def ingest_agent_event(
    event: AgentEvent,
    request: Request,
    authorization: str | None = Header(default=None),
    state: AppState = Depends(get_state),
):
    _check_token(state, authorization)
    full = state.hub.record_agent_event(event.model_dump())
    return AgentEventOut(**full)


@router.get("/agents/events", response_model=list[AgentEventOut])
def list_agent_events(limit: int = 100, before_id: int | None = None, state: AppState = Depends(get_state)):
    limit = max(1, min(limit, 500))
    rows = state.hub.store.list_agent_events(limit=limit, before_id=before_id)
    return [AgentEventOut(**r) for r in rows]


@router.get("/agents/events/stream")
async def stream_agent_events(request: Request, state: AppState = Depends(get_state)):
    """SSE feed for the frontend's observability dashboard — every new agent
    event lands here the moment it's ingested, so 'observe the agents' means
    a live feed, not a page the visitor has to keep reloading."""
    queue = state.hub.agent_event_broadcaster.subscribe()

    async def events():
        try:
            yield "event: ping\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"event: {item['type']}\ndata: {json.dumps(item['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            state.hub.agent_event_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
