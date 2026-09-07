# Deploying v2 (backend on Render, frontend on Vercel)

This is a runbook, not automation. It exists because this build was
prepared in a sandboxed environment with no route to Qdrant Cloud, GitHub,
Render, Vercel, or your Groq account — every step below needs to run on a
machine that has your actual credentials. Copy commands as-is; substitute
values in `<angle brackets>`.

Stack (unchanged from what was agreed): **Render** for the backend,
**Groq** for generation, **Qdrant Cloud** for the vector store, **Vercel**
for the frontend. No Azure resources are used here — the Azure student
credit is a separate track (Azure Container Apps remains a documented
alternative to Render in `README.md` and `backend/README.md` if you ever
want to compare cold-start behavior, but nothing in this runbook touches
it).

The repo is already committed locally on branch `main` (v1 static site +
v2 `backend/` and `frontend/`). Nothing has been pushed anywhere yet.

---

## 0. Prerequisites checklist

- [ ] A GitHub account/repo to push this to (can be the existing
      `02-tharuns.github.io` repo, since v1 keeps working from the same
      repo root — or a new repo if you'd rather keep v2 separate).
- [ ] A [Groq](https://console.groq.com/keys) API key.
- [ ] A [Qdrant Cloud](https://cloud.qdrant.io/) account (free tier: 1GB,
      plenty for 72 chunks).
- [ ] A [Render](https://render.com/) account (no card needed for the free
      tier).
- [ ] A [Vercel](https://vercel.com/) account.
- [ ] Python 3.12 and Node 22 on whatever machine you run the steps below
      on (needs real internet access — this sandbox does not have it).

---

## 1. Qdrant Cloud: create the cluster

1. In the Qdrant Cloud console, create a free cluster (any region close to
   Render's — Render's free tier runs in Oregon (US West) by default).
2. Copy the cluster's **URL** (looks like
   `https://xxxxx.us-east4-0.gcp.cloud.qdrant.io:6333`) and generate an
   **API key**. Save both — you'll set them as Render env vars in step 4.
3. You do **not** need to create the collection by hand — `ingest.py`
   calls `store.ensure_collection()` and creates it
   (`chappie_chunks`, 384-dim, cosine) on first run.

---

## 2. Groq: confirm the API key

1. Grab (or reuse) a key from the [Groq console](https://console.groq.com/keys).
2. Groq's free tier covers roughly 30 req/min and 1,000/day on
   `openai/gpt-oss-20b` — comfortably above what a portfolio site sees.

---

## 3. Run ingestion once, from a machine with real network access

This populates Qdrant and writes the final `backend/data/corpus.json` that
gets committed to git (same pattern as `assets/corpus.js` for v1 — the
deployed container never talks to `content/` directly, it just loads the
pre-built index).

```bash
cd backend
pip install -r requirements.txt
export QDRANT_URL="<your-cluster-url>"
export QDRANT_API_KEY="<your-qdrant-api-key>"
python3 ingest.py
```

Expected output ends with something like:

```
  embedded   72 chunks -> chappie_chunks
  qdrant count now: 72
```

The first run downloads two small ONNX models (`all-MiniLM-L6-v2` for
embeddings, `ms-marco-MiniLM-L-6-v2` for reranking) via `fastembed` —
a few tens of MB, cached locally after that.

Then commit the regenerated index:

```bash
git add backend/data/corpus.json
git commit -m "chore: run ingest.py, populate Qdrant + refresh corpus.json"
```

If `content/` ever changes later, re-run `ingest.py` and commit again —
same discipline as `scripts/build_corpus.py` for v1.

---

## 4. Push to GitHub

```bash
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

(If you're reusing `02-tharuns.github.io`, this is a normal push to the
same repo v1 already lives in — v1's GitHub Pages workflow
(`.github/workflows/deploy.yml`) only triggers on pushes to `main` and
only touches the static-site files, so it is unaffected by `backend/` and
`frontend/` landing alongside it.)

---

## 5. Deploy the backend to Render

1. Render dashboard → **New** → **Web Service** → connect the GitHub repo
   from step 4.
2. **Root directory**: `backend`
3. Render auto-detects the `Dockerfile` — leave build/start commands blank.
4. **Instance type**: Free.
5. Environment variables (Render → the service → Environment):

   | Key | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key |
   | `GROQ_MODEL` | `openai/gpt-oss-20b` |
   | `QDRANT_URL` | your Qdrant cluster URL |
   | `QDRANT_API_KEY` | your Qdrant API key |
   | `ALLOWED_ORIGIN` | `https://02-tharuns.github.io` for now — you'll add the Vercel URL after step 6 |
   | `AGENT_EVENTS_TOKEN` | any random string you generate (`openssl rand -hex 24`) — this is the shared secret the AI SRE agent project and the eval harness use to post to `/agents/events` and `/evals/runs` |
   | `CONTACT_NOTIFY_EMAIL` | where you want contact-form submissions emailed (optional) |
   | `SMTP_USER`, `SMTP_APP_PASSWORD` | a [Gmail App Password](https://myaccount.google.com/apppasswords) if you want contact/gap emails (optional — logs to stdout if unset) |

   Everything else has a safe default (see `backend/.env.example`).

6. Deploy. First boot on the free tier takes a minute or two (image build +
   ONNX model download). Confirm with:

   ```bash
   curl https://<your-service>.onrender.com/health
   ```

   Expect `{"ok": true, ...}`. Render's free tier spins the instance down
   after 15 minutes idle — the next request wakes it in about a minute;
   the frontend's chat widget already handles a slow/failed backend by
   falling back to extractive mode, so this is a UX trade-off, not a bug.

---

## 6. Deploy the frontend to Vercel

1. Vercel dashboard → **Add New** → **Project** → import the same repo.
2. **Root directory**: `frontend`
3. Vercel should auto-detect Vite; `vercel.json` already sets the build
   command (`npm run prebuild:content && npm run build`) and output dir
   (`dist`) and the SPA rewrite for React Router — no manual overrides
   needed.
4. Environment variable:

   | Key | Value |
   |---|---|
   | `VITE_API_BASE` | `https://<your-render-service>.onrender.com` |

5. Deploy. Note the resulting Vercel URL (e.g.
   `https://chappie-v2.vercel.app`).

---

## 7. Close the loop: update CORS

Back in Render → the backend service → Environment, update:

```
ALLOWED_ORIGIN=https://02-tharuns.github.io,https://<your-vercel-app>.vercel.app
```

(Comma-separated — both origins need to work: v1's GitHub Pages site and
v2's Vercel frontend, if you're keeping both live.) Save, which triggers a
redeploy.

---

## 8. Smoke test

```bash
curl https://<your-render-service>.onrender.com/health
```

Then open the Vercel URL, ask the chat widget a question that's actually
in `content/` (e.g. "what did you build for DARE-PM?"), and confirm:

- An answer streams back with a citation.
- The Observability page (`/observability`) shows the trace, the health
  cards populate, and the waterfall shows retrieval → fusion → rerank →
  generation stage timings.
- The Evals page (`/evals`) is empty until you run the harness (next
  step).

---

## 9. Run the eval suite against the live deployment (optional but recommended)

The default rate limits (6/min, 40/day/IP) will reject most of a 97-case
run fired in seconds. Either raise them temporarily via Render env vars
for the run, then set them back:

```bash
python3 evals/run_evals_api.py \
  --base https://<your-render-service>.onrender.com \
  --token <your-AGENT_EVENTS_TOKEN>
```

This publishes a run to `/evals/runs`, which is what populates the Evals
dashboard's history/chart. Expect the same bar v1 and local testing
already hit: 43/43 golden cases correctly sourced, 9/9 deflections safe,
0% attack success, 0% false refusal.

---

## 10. Optional: wire the AI SRE agent project

Whatever separate agent project you use to watch this service in
production should `POST` to:

```
https://<your-render-service>.onrender.com/agents/events
Authorization: Bearer <your-AGENT_EVENTS_TOKEN>
```

with a body matching `app/agents/routes.py`'s schema (`agent`, `kind`,
`severity`, `message`). Those events show up live in the Observability
page's "Agent events" column via SSE — no redeploy needed on this side to
start receiving them.

---

## What's deliberately NOT in this runbook

- **No CI secrets wiring.** `evals/run_evals_api.py` running as a GitHub
  Actions step against the live Render URL is a reasonable next step, but
  it needs `AGENT_EVENTS_TOKEN` (and a live, awake backend) as a repo
  secret — set that up yourself when/if you want it; not done here since
  it wasn't asked for and touches your GitHub repo's secrets.
- **No Azure resources.** Per your call to keep Render + Groq + Qdrant,
  none of the Azure student credit is spent by this runbook.
- **No custom domain.** Both Render and Vercel support one; add it in
  their respective dashboards once you're happy with the `.onrender.com`
  / `.vercel.app` URLs.
