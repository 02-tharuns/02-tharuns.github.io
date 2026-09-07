"""The question -> gates -> retrieval -> (generate) pipeline, shared by both
/ask and /ask/stream so the two endpoints can never disagree about what a
question is allowed to see. Mirrors assets/chatbot.js's `ask()` function
order exactly — see that file's header comment for the six-gate pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..deps import AppState
from ..guardrails import patterns as pat
from ..guardrails.gates import classify_intent
from ..observability.tracer import Trace
from ..retrieval.pipeline import Hit
from ..schemas import AskResponse, SourceChunk, Turn


@dataclass
class PendingGeneration:
    question: str
    hits: list[Hit]
    intent: str
    terms: list[str]

    @property
    def allowed_ids(self) -> set[str]:
        return {h.chunk.id for h in self.hits}


@dataclass
class PreparedAsk:
    early: AskResponse | None = None
    pending: PendingGeneration | None = None
    # For telemetry regardless of which branch fired.
    tokens: list[str] = field(default_factory=list)
    gap_topics: list[str] = field(default_factory=list)


def _hits_to_sources(hits: list[Hit]) -> list[SourceChunk]:
    return [
        SourceChunk(
            id=h.chunk.id, heading=h.chunk.heading, doc=h.chunk.doc, domain=h.chunk.domain,
            section=h.chunk.section, repo=h.chunk.repo, text=h.chunk.text, score=round(h.score, 4),
        )
        for h in hits
    ]


def prepare(text: str, state: AppState, trace: Trace) -> PreparedAsk:
    gr = state.guardrails

    with trace.span("sanitise"):
        clean, rej = gr.sanitise(text)
    if rej:
        return PreparedAsk(early=_refusal(gr, rej.code, rej.detail))

    with trace.span("injection_gate"):
        rej = gr.check_injection(clean)
    if rej:
        return PreparedAsk(early=_refusal(gr, rej.code, rej.detail))

    with trace.span("policy_gates"):
        rej = gr.check_task_request(clean) or gr.check_route(clean) or gr.check_personal(clean)
    if rej:
        return PreparedAsk(early=_refusal(gr, rej.code, rej.detail))

    hits, tokens, terms = state.pipeline.retrieve(clean, trace=trace)

    intent = classify_intent(clean)

    with trace.span("subject_analysis") as rec:
        subjects = gr.candidate_skill_terms(tokens)
        unknown_subjects = [t for t in subjects if not gr.is_known_term(t)]
        all_subjects_unknown = bool(subjects) and len(unknown_subjects) == len(subjects)
        rec["meta"] = {"subjects": subjects, "unknown": unknown_subjects}
        should_deflect = bool(subjects) and (
            (intent == "skill" and unknown_subjects) or all_subjects_unknown
        )
    if should_deflect:
        return _deflect(gr, tokens, clean, terms, hits)

    if pat.FIT_QUESTION.search(clean) and not unknown_subjects:
        with trace.span("fit_question_path") as rec:
            fit_terms = _fit_terms()
            fit_bm25 = gr.bm25.retrieve(fit_terms, candidates=state.pipeline.bm25_top_n)
            fit_hits = [Hit(chunk=h.chunk, score=h.score, bm25_raw=h.raw, source="bm25")
                        for h in fit_bm25 if h.score >= 0.34][:3]
            rec["meta"] = {"fit_hits": [h.chunk.id for h in fit_hits]}
        if fit_hits:
            fit_html = gr.compose("fit", fit_hits, fit_terms + terms)
            fit_ids = {h.chunk.id for h in fit_hits}
            if not gr.validate_citations(fit_html, fit_ids):
                return PreparedAsk(
                    early=AskResponse(ok=True, html=fit_html, sources=_hits_to_sources(fit_hits)),
                    tokens=tokens,
                )

    with trace.span("scope_gate"):
        rej = gr.check_scope(tokens, hits)
    if rej:
        return PreparedAsk(early=_refusal(gr, rej.code, rej.detail, hits), tokens=tokens)

    with trace.span("evidence_gate"):
        strong, rej = gr.check_evidence(hits)
    if rej:
        return _deflect(gr, tokens, clean, terms, hits)

    return PreparedAsk(pending=PendingGeneration(question=clean, hits=strong, intent=intent, terms=terms), tokens=tokens)


def finish_extractive(gr, pending: PendingGeneration) -> AskResponse:
    html = gr.compose(pending.intent, pending.hits, pending.terms)
    return AskResponse(ok=True, html=html, sources=_hits_to_sources(pending.hits))


def finish_generated(gr, pending: PendingGeneration, raw_answer: str) -> AskResponse:
    from ..generation.prompt import validate_generated
    validated = validate_generated(raw_answer, pending.allowed_ids)
    if validated == "NO_EVIDENCE":
        return finish_extractive(gr, pending)
    html = gr.render_citations(validated, pending.hits)
    rej = gr.validate_citations(html, pending.allowed_ids)
    if rej:
        return finish_extractive(gr, pending)
    return AskResponse(ok=True, html=html, answer=validated, sources=_hits_to_sources(pending.hits))


def _refusal(gr, code: str, detail: str, hits: list[Hit] | None = None) -> AskResponse:
    return AskResponse(ok=False, code=code, html=gr.refusal_html(code))


def _fit_terms() -> list[str]:
    from ..textproc import expand, tokenise
    query = pat.FIT_QUERY
    return expand(tokenise(query), query)


def _deflect(gr, tokens: list[str], question: str, terms: list[str], hits: list[Hit]) -> PreparedAsk:
    topics = gr.unknown_terms(question)
    adjacent = gr.nearest_strength(tokens, question)
    html = gr.compose_deflection(topics, adjacent, terms)
    return PreparedAsk(
        early=AskResponse(ok=False, code="not_published", html=html),
        tokens=tokens, gap_topics=topics,
    )
