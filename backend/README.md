# Chappie backend (v2)

FastAPI service owning **contact, retrieval, and generation** — the
counterpart to the [frontend](../frontend/README.md) React app and the
successor to the old generation-only `backend/app.py` (still present in
git history; the legacy request/response shape is documented in
`_legacy_app_reference.py.bak` for reference during the migration).

## What changed from v1

v1 (still live under `assets/chatbot.js` + GitHub Pages) does retrieval in
the visitor's browser: BM25 over a prebuilt JSON index, and optionally an
already-retrieved-passages POST to a generation-only backend. v2 moves
retrieval here too, and makes it hybrid:

```
question --> guardrail gates (ported from chatbot.js, unchanged behavior)
         --> BM25 (lexical)  ----\
         --> Qdrant (dense)  -----> Reciprocal Rank Fusion --> cross-encoder rerank
         --> confidence score (still the calibrated BM25 0..1 scale)
         --> evidence gate --> Groq generation (or extractive fallback)
         --> citation validation --> traced end to end (SQLite + SSE)
```

See `app/retrieval/pipeline.py`'s module docstring for why BM25 stays the
gates' confidence signal even though dense retrieval and reranking now
decide which chunks are actually selected.

## Layout

```
app/
  config.py            All env vars, one dataclass.
  textproc.py           Tokeniser/stemmer/expansions/chunker — mirrors
                        scripts/build_corpus.py and assets/chatbot.js.
  schemas.py             Pydantic request/response models.
  deps.py                Builds the AppState singleton (BM25 index, hybrid
                        pipeline, guardrails, Groq client, observability
                        hub) and hands it to routers via Depends(get_state).
  retrieval/             bm25.py, embeddings.py (fastembed), vectorstore.py
                        (Qdrant Cloud / in-memory), fusion.py (RRF),
                        reranker.py (fastembed cross-encoder), pipeline.py
                        (orchestrates all of the above + tracing).
  guardrails/             patterns.py + gates.py — the six gates and
                        extractive/deflection composition, ported from
                        assets/chatbot.js gate-for-gate.
  generation/             prompt.py (SYSTEM prompt, unchanged from v1) +
                        groq_client.py (httpx, streaming + non-streaming).
  observability/          store.py (SQLite), tracer.py (per-request Trace +
                        SSE pub/sub), routes.py (GET endpoints the
                        frontend's Observability page polls/streams).
  agents/                 routes.py — POST /agents/events, the ingestion
                        endpoint the separate AI SRE agent project posts to.
  contact/                routes.py — POST /contact, the site's contact form.
  ask/                    pipeline_runner.py (the ask() pipeline, shared by
                        both endpoints) + routes.py (POST /ask, /ask/stream,
                        /gap, GET /health).
  evals/                  routes.py — GET/POST /evals/runs, backing the
                        frontend's Evals page.
  main.py                 create_app() factory + module-level `app`.
ingest.py                 content/*.md -> BM25 corpus.json + Qdrant Cloud
                        (or --dry-run for an in-memory smoke test).
tests/                    52 tests, all against fakes — see conftest.py.
```

## Why fastembed, not sentence-transformers

`sentence-transformers` (already installed in this dev environment for
other reasons) pulls in torch, which alone pushes a process well past a
Render free-tier instance's ~512MB RAM even for a tiny model. `fastembed`
runs the same small ONNX-exported models (`sentence-transformers/all-MiniLM-L6-v2`
for embeddings, `Xenova/ms-marco-MiniLM-L-6-v2` for reranking) through
`onnxruntime` instead — tens of MB, not hundreds — which is the difference
between fitting in a free instance and not.

## Local development

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in what you have; everything has a safe default
python3 ingest.py --dry-run    # builds data/corpus.json, skips Qdrant/fastembed
                                # (use this if you don't have Qdrant Cloud /
                                # network access yet — BM25-only still works)
uvicorn app.main:app --reload --port 8000
```

Without `GROQ_API_KEY` set, `/ask` always answers extractively (quotes, no
generation) — exactly like the v1 static build's default. Without
`QDRANT_URL`, dense retrieval falls back to an empty in-memory store and
the pipeline degrades to BM25-only automatically (see
`app/retrieval/pipeline.py`'s "degrading gracefully" note).

## Tests

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

All 52 tests run against fakes (`DeterministicFakeEmbedder`,
`InMemoryVectorStore`, `LexicalOverlapReranker`, `FakeGroqClient` in
`tests/conftest.py`) — no network call, no API key, no Qdrant Cloud needed.
Real Qdrant/fastembed/Groq behavior is exercised in CI (full internet) and
in the deployed service, exactly like `scripts/build_corpus.py`'s
CI-only verification already worked for the v1 static build.

## Evaluating

```bash
python3 ../evals/run_evals_api.py --base http://127.0.0.1:8000
```

Runs the same 97-case suite (`evals/suites.json`) the v1 Playwright harness
checks, now against the live HTTP API, and publishes the result to
`/evals/runs` (set `EVAL_INGEST_TOKEN`/`AGENT_EVENTS_TOKEN`) so the
frontend's Evals page has history to chart.

**Rate limits during an eval run**: the harness fires ~97 requests from one
IP in seconds — the default `RATE_LIMIT_PER_DAY=40` will reject most of
them. Run the server for eval purposes with generous limits:

```bash
RATE_LIMIT_PER_MIN=1000 RATE_LIMIT_PER_DAY=5000 RATE_LIMIT_GLOBAL_PER_DAY=5000 \
  uvicorn app.main:app --port 8000
```

(Verified end to end in this exact configuration: 43/43 golden, 9/9
deflections, 0% attack success, 0% false refusal, 100% recall@3/no-answer
accuracy/citation correctness — the full bar the v1 build already cleared.)

## Deploying

**Render** (recommended, matches v1's README): connect the repo, root
directory `backend/`, it auto-detects the `Dockerfile`. Run
`python3 ingest.py` locally or in a one-off CI job first and commit
`data/corpus.json` (same pattern as `assets/corpus.js` in v1) — the
container only needs `backend/`, not `../content`, at runtime (see the
Dockerfile's comment).

Environment variables: see `.env.example` for the full list. At minimum for
a working generated+hybrid deployment: `GROQ_API_KEY`, `QDRANT_URL`,
`QDRANT_API_KEY`, `ALLOWED_ORIGIN` (your Vercel frontend's origin),
`AGENT_EVENTS_TOKEN` (shared secret for the SRE agent project + the evals
harness).
