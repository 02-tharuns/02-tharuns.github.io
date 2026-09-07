# Chappie v2 — hybrid retrieval, a real backend, and two dashboards

`ARCHITECTURE.md` describes v1: a static site where the browser does BM25
retrieval itself and, optionally, a thin generation-only backend fills in
prose. That build still exists, still passes its own eval suite, and is
still the right answer for "I want zero infrastructure." This document
describes v2, which exists because a portfolio piece about applied ML
should demonstrate more of what applied ML actually looks like: hybrid
retrieval, a reranking stage, and observability you can point a recruiter
at instead of just describing.

---

## 1. What moved, and why

| | v1 (static) | v2 (this document) |
|---|---|---|
| Frontend | Hand-written HTML/CSS/JS, GitHub Pages | React + TypeScript + Vite, Vercel |
| Retrieval | BM25 only, in the browser | Hybrid: BM25 + Qdrant dense, fused (RRF), reranked (cross-encoder) — server-side |
| Generation | Optional, thin backend | Same Groq model, now wired to hybrid retrieval |
| Contact form | None | `POST /contact`, backend-owned |
| Observability | `window.__RAG_LOG` in the console | A live dashboard: per-stage trace waterfall + external agent event feed |
| Evals | Playwright harness, console output only | Python harness against the live API, published to a dashboard with history |

Retrieval moved server-side because a cross-encoder reranker and a Qdrant
Cloud client are not things a browser should be loading — the v1 constraint
("no server, no cold start") was a deliberate trade-off for a
zero-infrastructure deploy, not a belief that client-side retrieval is
better. v2 spends the infrastructure v1 avoided, in exchange for retrieval
quality and observability v1 structurally can't have (there is nowhere to
put a trace of "what did the reranker do" in a browser console line).

The **guardrail gates did not move conceptually** — `backend/app/guardrails/`
is a direct, gate-for-gate port of `assets/chatbot.js`'s six-gate pipeline,
verified against the *same* 97-case eval suite (`evals/suites.json`) v1
already used, via the new `evals/run_evals_api.py` harness. That run
reached the identical bar v1 holds: 43/43 golden cases correctly sourced,
9/9 deflections safe, 0% attack success, 0% false refusal, 100% recall@3 /
no-answer accuracy / citation correctness. The port is behaviorally
verified, not just structurally similar.

---

## 2. Request path

```
Vercel (React)                    Render (FastAPI)                  Qdrant Cloud / Groq
───────────────                   ─────────────────                 ────────────────────
question typed in
the chat widget
        │
        │ POST /ask/stream
        ▼
                                   gate 0-2: sanitise, injection,
                                   task/route/personal policy
                                             │
                                             ├─ BM25 (lexical, in-process)
                                             ├─ Qdrant dense search  ───────► Qdrant Cloud
                                             │        │
                                             ▼        ▼
                                   Reciprocal Rank Fusion
                                             │
                                             ▼
                                   cross-encoder rerank (fastembed, ONNX)
                                             │
                                   gate 3: evidence floor (BM25-calibrated
                                   confidence — see pipeline.py docstring)
                                             │
                                             ▼
                                   Groq chat/completions (stream)  ───────► Groq
                                             │
                                   gate 5: citation validation
        ◄────────────────────────────────────┘
render tokens, then the
authoritative verdict
        │
        │ (every stage above recorded as a span)
        ▼
                                   SQLite: traces, agent_events, eval_runs
                                             │
        ◄─── GET /observability/stream ──────┘  (SSE, live)
        ◄─── GET /agents/events/stream ───────┘  (SSE, live)
        ◄─── GET /evals/runs ─────────────────┘  (poll)
```

Every stage — gates, BM25, dense retrieval, fusion, reranking, generation —
is one `trace.span(...)` in `backend/app/observability/tracer.py`. The
Observability page's waterfall is that span list rendered as proportional
bars; nothing is synthesized for the dashboard, it's the actual pipeline's
own timing.

## 3. "Observe the agents"

The request also asked to observe *agents*, not just this pipeline. Rather
than couple this codebase to a specific agent framework, `backend/app/agents/routes.py`
exposes a deliberately thin, bearer-token-protected ingestion endpoint
(`POST /agents/events`: agent name, event kind, severity, free-form message
+ payload) that the separate AI SRE agent project posts to independently.
This service stores what it's told and renders it live next to the RAG
pipeline's own traces — the two systems share a dashboard without sharing a
release cycle. See `claude/chappie-*.md` and the AI SRE agent project's own
roadmap doc for what that project observes and why.

## 4. Evaluating on the site itself

`evals/run_evals_api.py` runs the same 97-case suite against the live
`/ask` endpoint and POSTs the finished run — pass/fail counts, the four
headline metrics, and every individual case — to `POST /evals/runs`. The
Evals page charts that history and lets you drill into any run's failures.
Point this harness at your CI pipeline (after deploy, or as a smoke test
before promoting a deploy) and "evaluate on the site" becomes literal: the
dashboard is the eval report, not a GitHub Actions log nobody reads after
day one.

## 5. Where this exceeds a typical RAG crash course

`claude/portfolio-rag-azure-build-plan.md` already lays out, section by
section, where the first Krish Naik crash course referenced during this
build stops (retrieval quality, guardrails, evaluation, observability) and
what a production system needs beyond it. v2 is that gap closed for one
real system: hybrid retrieval instead of a single retriever, a reranking
stage, six behaviorally-verified guardrail gates (not a system prompt
asking nicely), a citation-validation gate that discards ungrounded
generations rather than trusting them, and observability/evals as
first-class product surfaces rather than a `print()` statement. The second,
larger course (LangChain v1 middleware, LangGraph Deep Agents, LangSmith
evaluation, LiteLLM gateways) supplied useful *framing* — the
`agents/routes.py` ingestion contract is deliberately middleware-shaped,
and `evals/run_evals_api.py`'s "publish a run for dashboard history" idea
mirrors LangSmith's dataset+experiment pattern — but this build reaches
those outcomes with the dependencies already justified above (fastembed
over sentence-transformers, a direct Groq client over LiteLLM) rather than
adopting a framework for its own sake. A framework earns its place when it
removes real complexity; a single-provider `httpx` client and a bespoke
72-line SQLite tracer were less complexity than the frameworks that
replace them, not more.

## 6. Known trade-offs, stated plainly

- **Rate limiting is in-memory, per-instance** (`backend/app/ratelimit.py`)
  — inherited unchanged from v1's backend. Fine for a single free-tier
  instance; the first thing to swap for something shared if this ever runs
  with more than one replica.
- **SQLite, not Postgres**, backs traces/agent-events/eval-runs — a
  one-person portfolio service's traffic doesn't justify a managed
  database. Same reasoning as the rate limiter.
- **BM25 stays the gates' confidence signal** even after adding dense
  retrieval and reranking — not a limitation so much as a deliberate
  choice to keep the calibrated thresholds (`evidenceFloor`,
  `scopeCoverageFloor`) meaningful. See `backend/app/retrieval/pipeline.py`.
- **fastembed over sentence-transformers/torch** for the same reason
  small-model choices were made in the original build plan: Render's free
  tier has ~512MB RAM, and torch alone doesn't leave much room for
  anything else running in the same process.
