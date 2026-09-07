"""GET endpoints backing the frontend's observability dashboard: recent
trace waterfalls for the RAG pipeline itself, plus a live SSE feed so new
traces (and, via agents/routes.py, agent events) appear without polling."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ..deps import AppState, get_state
from ..schemas import TraceOut

router = APIRouter()


@router.get("/observability/traces", response_model=list[TraceOut])
def list_traces(limit: int = 50, before: str | None = None, state: AppState = Depends(get_state)):
    limit = max(1, min(limit, 200))
    return state.hub.store.list_traces(limit=limit, before=before)


@router.get("/observability/traces/{trace_id}", response_model=TraceOut)
def get_trace(trace_id: str, state: AppState = Depends(get_state)):
    trace = state.hub.store.get_trace(trace_id)
    if not trace:
        from fastapi import HTTPException
        raise HTTPException(404, "Trace not found.")
    return trace


@router.get("/observability/stream")
async def stream_traces(request: Request, state: AppState = Depends(get_state)):
    queue = state.hub.trace_broadcaster.subscribe()

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
            state.hub.trace_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
