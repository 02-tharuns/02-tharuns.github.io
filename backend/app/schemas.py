"""Pydantic models shared across routers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(max_length=400)
    # History only — retrieval now happens server-side, so the client no
    # longer sends contexts. Kept optional so an old cached frontend build
    # calling with `contexts` doesn't hard-fail; the field is simply unused.
    history: list[Turn] = Field(default_factory=list, max_length=6)


class SourceChunk(BaseModel):
    id: str
    heading: str
    doc: str
    domain: str = ""
    section: str = ""
    repo: str = ""
    text: str
    score: float


class AskResponse(BaseModel):
    ok: bool
    code: str | None = None
    html: str
    answer: str | None = None
    sources: list[SourceChunk] = Field(default_factory=list)
    trace_id: str | None = None


class GapReport(BaseModel):
    question: str = Field(max_length=400)
    topics: list[str] = Field(default_factory=list, max_length=12)


class ContactRequest(BaseModel):
    name: str = Field(max_length=120)
    email: str = Field(max_length=200)
    message: str = Field(max_length=3000)
    honeypot: str = Field(default="", max_length=200)  # bot trap, must stay empty


class ContactResponse(BaseModel):
    ok: bool
    detail: str = ""


class ReportRequest(BaseModel):
    """A visitor (typically a recruiter) flagging that an answer was wrong,
    unclear, or didn't address their question. Distinct from GapReport: a
    gap is the bot itself noticing it has no evidence; a report is a human
    overriding the bot's own confidence after reading the answer it gave."""

    trace_id: str | None = Field(default=None, max_length=64)
    question: str = Field(max_length=400)
    answer_text: str = Field(default="", max_length=4000)
    reason: str = Field(default="", max_length=1000)
    contact_email: str = Field(default="", max_length=200)
    honeypot: str = Field(default="", max_length=200)  # bot trap, must stay empty


class ReportResponse(BaseModel):
    ok: bool
    detail: str = ""


class ReportOut(BaseModel):
    """Public shape of a stored report. Deliberately omits contact_email —
    a recruiter volunteering their address for a follow-up shouldn't have it
    show up on a dashboard any site visitor can load; the full record
    (including the email) only ever leaves this service in the notification
    sent to the owner."""

    id: int
    received_at: str
    trace_id: str | None = None
    question: str
    answer_text: str = ""
    reason: str = ""


class AgentEvent(BaseModel):
    """One observation posted by the separate AI SRE agent project.

    Deliberately loose (`payload: dict[str, Any]`) — the SRE agent is a
    different codebase evolving on its own schedule, and this endpoint's job
    is to display what it sends, not to gatekeep its shape. `agent`, `kind`
    and `severity` are the only fields the dashboard groups/filters by.
    """

    agent: str = Field(max_length=80)
    kind: str = Field(max_length=80)
    severity: Literal["info", "warning", "error", "critical"] = "info"
    message: str = Field(max_length=2000)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentEventOut(AgentEvent):
    id: int
    received_at: str


class TraceSpanOut(BaseModel):
    name: str
    started_at: float
    duration_ms: float
    meta: dict[str, Any] = Field(default_factory=dict)


class TraceOut(BaseModel):
    id: str
    started_at: str
    duration_ms: float
    question: str
    verdict: str
    reason: str | None = None
    score: float | None = None
    spans: list[TraceSpanOut] = Field(default_factory=list)


class EvalRunSummary(BaseModel):
    id: str
    started_at: str
    duration_ms: float
    suite_counts: dict[str, int] = Field(default_factory=dict)
    attack_success_rate: float
    false_refusal_rate: float
    recall_at_k: float
    no_answer_accuracy: float
    citation_correctness: float
    # Optional + defaulted to None: older published runs (before these
    # categories existed) don't have them, and "n/a" beats a fake 0%.
    answer_relevancy: float | None = None
    role_adherence: float | None = None
    knowledge_retention: float | None = None
    conversation_completeness: float | None = None
    passed: bool
    git_sha: str | None = None


class EvalRunDetail(EvalRunSummary):
    cases: list[dict[str, Any]] = Field(default_factory=list)
