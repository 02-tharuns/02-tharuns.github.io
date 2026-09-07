"""Per-request tracing for the /ask pipeline, plus a tiny pub-sub hub so the
frontend's observability dashboard can watch traces and agent events land in
real time (SSE) instead of only polling the SQLite-backed history.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from .store import Store


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Trace:
    """One /ask call. `with trace.span("retrieve_bm25"):` wraps a pipeline
    stage; the span's wall-clock duration and any meta passed in are recorded
    for the trace waterfall the frontend renders."""

    def __init__(self, question: str):
        self.id = uuid.uuid4().hex[:16]
        self.question = question
        self.started_at = _now_iso()
        self._t0 = time.perf_counter()
        self.spans: list[dict[str, Any]] = []
        self.verdict: str | None = None
        self.reason: str | None = None
        self.score: float | None = None

    @contextmanager
    def span(self, name: str, **meta: Any):
        start = time.perf_counter()
        offset_ms = (start - self._t0) * 1000
        record: dict[str, Any] = {"name": name, "started_at": offset_ms, "meta": meta}
        try:
            yield record
        finally:
            record["duration_ms"] = (time.perf_counter() - start) * 1000
            self.spans.append(record)

    def finish(self, verdict: str, reason: str | None = None, score: float | None = None) -> dict:
        self.verdict = verdict
        self.reason = reason
        self.score = score
        duration_ms = (time.perf_counter() - self._t0) * 1000
        return {
            "id": self.id, "started_at": self.started_at, "duration_ms": duration_ms,
            "question": self.question, "verdict": verdict, "reason": reason, "score": score,
            "spans": self.spans,
        }


class _Broadcaster:
    """Fan-out to any number of SSE subscribers. A slow/gone subscriber never
    blocks the request that produced the event — queues are bounded and a
    full queue just drops the oldest event for that one subscriber."""

    def __init__(self, maxsize: int = 64):
        self._subscribers: set[asyncio.Queue] = set()
        self._maxsize = maxsize

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, event: dict) -> None:
        for q in list(self._subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


class ObservabilityHub:
    """One instance lives on app.state for the process lifetime. Owns the
    SQLite store, an in-memory ring buffer for fast "recent traces" reads,
    and the SSE broadcasters for both traces and external agent events."""

    def __init__(self, db_path: str, ring_buffer_size: int = 200):
        self.store = Store(db_path)
        self.recent_traces: deque[dict] = deque(maxlen=ring_buffer_size)
        self.trace_broadcaster = _Broadcaster()
        self.agent_event_broadcaster = _Broadcaster()
        self.report_broadcaster = _Broadcaster()

    def record_trace(self, trace_dict: dict) -> None:
        self.recent_traces.appendleft(trace_dict)
        self.store.insert_trace(trace_dict)
        self.trace_broadcaster.publish({"type": "trace", "data": trace_dict})

    def record_agent_event(self, event: dict) -> dict:
        event = {**event, "received_at": _now_iso()}
        event_id = self.store.insert_agent_event(event)
        full = {**event, "id": event_id}
        self.agent_event_broadcaster.publish({"type": "agent_event", "data": full})
        return full

    def record_report(self, report: dict) -> dict:
        report = {**report, "received_at": _now_iso()}
        report_id = self.store.insert_report(report)
        full = {**report, "id": report_id}
        # Broadcast the public shape only — never the recruiter's own email
        # address to every dashboard viewer (see schemas.ReportOut).
        public = {k: v for k, v in full.items() if k != "contact_email"}
        self.report_broadcaster.publish({"type": "report", "data": public})
        return full
