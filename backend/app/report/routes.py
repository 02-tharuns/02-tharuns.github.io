"""POST /report — a visitor (typically a recruiter) flags an answer as
wrong, unclear, or not what they asked for. Separate from POST /gap
(ask/routes.py): a gap report is the bot itself noticing it had no evidence
and deflecting; a /report is a human overriding the bot's own confidence
after actually reading what it said — the failure mode the automated eval
suite structurally can't catch, because it doesn't know what a real
recruiter finds unclear, wrong, or unconvincing.

Modeled directly on contact/routes.py: same honeypot trap, same shared
rate limiter, no hard validation beyond "there has to be a question" so a
frustrated visitor can't be blocked by a picky form. Every report is stored
(so the Observability dashboard can show a "visitor reports" feed) and
best-effort emailed to the owner; a duplicate report of the same trace
within the dedupe window is stored again (so the count is honest) but only
emailed once, the same anti-spam pattern GapDeduper already uses for /gap.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse

from ..deps import AppState, get_state
from ..notify import send_report_email
from ..schemas import ReportOut, ReportRequest, ReportResponse

router = APIRouter()


@router.post("/report", response_model=ReportResponse)
async def submit_report(
    body: ReportRequest, request: Request, background: BackgroundTasks, state: AppState = Depends(get_state)
):
    state.rate_limiter.check(request)

    if body.honeypot.strip():
        # Same silent-success bot trap as /contact — no signal to whatever
        # filled every field that it was caught.
        return ReportResponse(ok=True)

    question = body.question.strip()
    if not question:
        return ReportResponse(ok=False, detail="Missing the question that was reported.")

    state.hub.record_report(
        {
            "trace_id": body.trace_id,
            "question": question,
            "answer_text": body.answer_text.strip(),
            "reason": body.reason.strip(),
            "contact_email": body.contact_email.strip(),
        }
    )

    dedupe_key = body.trace_id or question.lower()
    if not state.report_deduper.is_duplicate(dedupe_key):
        background.add_task(
            send_report_email,
            state.settings,
            question,
            body.answer_text.strip(),
            body.reason.strip(),
            body.trace_id,
            body.contact_email.strip(),
        )

    return ReportResponse(ok=True, detail="Thanks — flagged for review.")


@router.get("/report", response_model=list[ReportOut])
def list_reports(limit: int = 50, before_id: int | None = None, state: AppState = Depends(get_state)):
    limit = max(1, min(limit, 200))
    rows = state.hub.store.list_reports(limit=limit, before_id=before_id)
    return [ReportOut(**r) for r in rows]


@router.get("/report/stream")
async def stream_reports(request: Request, state: AppState = Depends(get_state)):
    """SSE feed so the Observability page's reports panel updates live,
    exactly like the trace and agent-event feeds it sits alongside."""
    queue = state.hub.report_broadcaster.subscribe()

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
            state.hub.report_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
