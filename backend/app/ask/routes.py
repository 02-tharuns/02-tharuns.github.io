"""POST /ask, POST /ask/stream, POST /gap, GET /health.

Retrieval now happens here (server-side, hybrid) rather than in the browser,
so the request body no longer carries `contexts` — see schemas.AskRequest.
"""

from __future__ import annotations

import json

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse

from ..deps import AppState, get_state
from ..generation.groq_client import GroqError, estimate_cost_usd
from ..generation.prompt import build_messages

# Generation is a best-effort enhancement on top of extractive answering,
# never a hard dependency — the product worked before this backend existed
# by quoting sources, and it must keep working exactly that way the moment
# Groq is unconfigured, rate-limited, or unreachable. Any failure here (bad
# status, timeout, DNS, connection refused) falls back to compose(), never
# a 500 to the visitor.
GENERATION_FAILURE = (GroqError, httpx.HTTPError)
from ..notify import send_gap_email
from ..observability.tracer import Trace
from ..schemas import AskRequest, AskResponse, GapReport
from .pipeline_runner import finish_extractive, finish_generated, prepare

router = APIRouter()


@router.get("/health")
def health(state: AppState = Depends(get_state)):
    return {
        "ok": True,
        "model": state.settings.groq_model,
        "dense_retrieval": state.pipeline.use_dense,
        "reranker": state.settings.use_reranker,
    }


@router.post("/gap")
async def gap(report: GapReport, request: Request, background: BackgroundTasks, state: AppState = Depends(get_state)):
    state.rate_limiter.check(request)
    if not state.gap_deduper.is_duplicate(report.question):
        background.add_task(send_gap_email, state.settings, report.question, report.topics)
    return {"ok": True}


def _record_usage(rec: dict, model: str, usage: dict | None) -> None:
    """Token Cost Tracking: fold Groq's usage block into the "generate"/
    "generate_stream" span's meta, so the observability dashboard can read
    cost straight off the trace it already stores — no new table, no new
    endpoint. Silently a no-op if usage wasn't reported (e.g. an older Groq
    response shape) or the model isn't in the pricing table."""
    if not usage:
        return
    rec["meta"]["prompt_tokens"] = usage.get("prompt_tokens")
    rec["meta"]["completion_tokens"] = usage.get("completion_tokens")
    cost = estimate_cost_usd(model, usage)
    if cost is not None:
        rec["meta"]["cost_usd"] = cost


def _record(state: AppState, trace: Trace, response: AskResponse, gap_topics: list[str]) -> None:
    top_score = response.sources[0].score if response.sources else None
    trace_dict = trace.finish(verdict=response.code or "allow", reason=None, score=top_score)
    state.hub.record_trace(trace_dict)
    if response.code == "not_published" and gap_topics:
        if not state.gap_deduper.is_duplicate(trace.question):
            send_gap_email(state.settings, trace.question, gap_topics)


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request, state: AppState = Depends(get_state)):
    state.rate_limiter.check(request)
    trace = Trace(question=body.question)
    prepared = prepare(body.question, state, trace)

    if prepared.early:
        prepared.early.trace_id = trace.id
        _record(state, trace, prepared.early, prepared.gap_topics)
        return prepared.early

    pending = prepared.pending
    if not state.settings.groq_api_key:
        with trace.span("extractive_no_key"):
            response = finish_extractive(state.guardrails, pending)
    else:
        try:
            with trace.span("generate", model=state.settings.groq_model) as rec:
                messages = build_messages(pending.question, pending.hits, body.history)
                raw, usage = await state.groq.complete(messages)
                _record_usage(rec, state.settings.groq_model, usage)
            response = finish_generated(state.guardrails, pending, raw)
        except GENERATION_FAILURE:
            with trace.span("extractive_fallback"):
                response = finish_extractive(state.guardrails, pending)
    response.trace_id = trace.id
    _record(state, trace, response, [])
    return response


@router.post("/ask/stream")
async def ask_stream(body: AskRequest, request: Request, state: AppState = Depends(get_state)):
    state.rate_limiter.check(request)
    trace = Trace(question=body.question)
    prepared = prepare(body.question, state, trace)

    if prepared.early:
        prepared.early.trace_id = trace.id
        _record(state, trace, prepared.early, prepared.gap_topics)
        payload = prepared.early.model_dump()

        async def early_events():
            yield f"event: verdict\ndata: {json.dumps(payload)}\n\n"

        return StreamingResponse(early_events(), media_type="text/event-stream")

    pending = prepared.pending
    guardrails = state.guardrails

    async def events():
        collected: list[str] = []
        if not state.settings.groq_api_key:
            with trace.span("extractive_no_key"):
                response = finish_extractive(guardrails, pending)
        else:
            try:
                with trace.span("generate_stream", model=state.settings.groq_model) as rec:
                    messages = build_messages(pending.question, pending.hits, body.history)
                    usage_sink: dict = {}
                    async for piece in state.groq.stream(messages, usage_sink=usage_sink):
                        collected.append(piece)
                        yield f"event: token\ndata: {json.dumps({'t': piece})}\n\n"
                    _record_usage(rec, state.settings.groq_model, usage_sink or None)
                response = finish_generated(guardrails, pending, "".join(collected))
            except GENERATION_FAILURE:
                with trace.span("extractive_fallback"):
                    response = finish_extractive(guardrails, pending)
        response.trace_id = trace.id
        _record(state, trace, response, [])
        yield f"event: verdict\ndata: {response.model_dump_json()}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
