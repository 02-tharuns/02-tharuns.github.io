# Chappie frontend (v2)

React + TypeScript + Vite, deployed to Vercel. Three surfaces:

- **`/`** — the portfolio itself, rendered from `../content/*.md` (the same
  source of truth the backend's `ingest.py` and the v1 static build's
  `scripts/build_corpus.py` read — see `scripts/build-content.mjs`), plus
  the Chappie chat widget.
- **`/observability`** — a live trace waterfall of every `/ask` call's
  pipeline stages (gates, BM25, dense retrieval, RRF fusion, reranking,
  generation), and a live feed from the separate AI SRE agent project
  posting to `POST /agents/events`.
- **`/evals`** — eval run history (`GET /evals/runs`), charted, with
  per-case drill-down — the frontend half of `evals/run_evals_api.py`.

## Local development

```bash
cd frontend
npm install
npm run dev
```

`.env.development` already points `VITE_API_BASE` at
`http://127.0.0.1:8000` — run the [backend](../backend/README.md) locally
first (`uvicorn app.main:app --reload --port 8000`), including its
`ALLOWED_ORIGIN` covering `http://localhost:5173`.

`npm run dev` and `npm run build` both regenerate
`src/data/content.generated.json` from `../content/*.md` first
(`prebuild:content` in package.json) — edit the Markdown, not the
generated JSON.

## Building

```bash
npm run build   # tsc -b && vite build, content regenerated first
npm run preview # serve dist/ locally to sanity-check the production build
```

Verified end to end with a headless-browser smoke test against a live
backend: portfolio content renders from `content/*.md`, the chat widget
streams an answer with a cited source card, the Observability page renders
a real trace waterfall, and the Evals page renders published run metrics.

## Deploying (Vercel)

`vercel.json` sets the build command (`prebuild:content` then `build`),
output directory (`dist`), and SPA rewrite (all paths serve `index.html`,
required for React Router's `/observability` and `/evals` routes to work
on a hard refresh or direct link).

Set `VITE_API_BASE` as a Vercel project environment variable to your
deployed backend's URL (Render, Azure Container Apps, ...) — see
`.env.production.example`.
