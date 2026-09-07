# How Chappie is built (v1, static)

This document covers the original static build: GitHub Pages, browser-only
BM25 retrieval, an optional thin generation backend. It's still accurate
and this build still works. For the hybrid-retrieval React/FastAPI build
with observability and evals dashboards, see
[`V2_ARCHITECTURE.md`](V2_ARCHITECTURE.md) instead.

Nothing here is hardcoded. Every answer is retrieved at request time from an
index built out of `content/`. Change a Markdown file, rebuild, and the answers
change. What made it *feel* hardcoded is that the default answering mode quotes
sentences verbatim instead of composing prose. That is a switch, and this
document explains where it is.

---

## 1. The one idea: two runtimes

Almost all confusion about this system comes from collapsing two separate
programs into one picture.

**Build time** is Python on your machine. It runs when you edit content, never
when a visitor asks a question. It reads Markdown and writes one static file.

**Request time** is JavaScript in the visitor's browser. It never touches your
Markdown. It loads the file the first program produced and does arithmetic
against it.

```
BUILD TIME  ·  python3 scripts/build_corpus.py  ·  once per content edit
────────────────────────────────────────────────────────────────────────
   content/*.md ──► chunk on "##" ──► tokenise + stem ──► count tf, df, avgdl
                                                                │
                                                                ▼
                                                   assets/corpus.js  (67 KB)
                                                   committed to git
                                                                │
────────────────────────────────────────────────────────────────┼────────
REQUEST TIME  ·  the visitor's browser  ·  once per question    │
────────────────────────────────────────────────────────────────┼────────
                                                                ▼
   question ─► gate 0 ─► gate 1 ─► gate 2 ─► BM25 score ─► gate 3 ─► answer
              hygiene  injection   scope    (~0.5 ms)    evidence
```

The browser keeps retrieval because the index is 67 KB and scoring it takes
about half a millisecond. Shipping it to the client removes a network
round-trip from every question and keeps the site working with no server at
all.

---

## 2. File structure

```
content/                    SOURCE OF TRUTH. Plain Markdown, YAML front-matter.
  00-profile.md             Every "## heading" becomes one retrievable passage.
  10-education.md           Edit these to change what Chappie can say.
  2x-project-*.md           One file per project.
  30-skills.md
  60-posture.md             volunteer: false — only surfaces when triggered.
  62-llm-genai.md           The LLM / RAG / Chappie-itself passages.

scripts/
  build_corpus.py           Ingestion. Chunk, tokenise, stem, BM25 stats.
                            Its stemmer is mirrored byte-for-byte in the client.

assets/
  corpus.js                 GENERATED. window.__RAG_CORPUS = { N, avgdl, df, chunks }.
                            Do not hand-edit. Commit it alongside content/.
  chatbot.js                The whole client: tokeniser, expansion, BM25,
                            six gates, extractive composition, streaming
                            client, and the UI.
  chatbot.css               Widget styling. Inherits the site's design tokens.

evals/
  suites.json               97 cases in four groups.
  run_evals.mjs             Drives the real page in headless Chromium.

backend/                    OPTIONAL. Only needed for generated answers.
  app.py                    FastAPI. Holds the API key. /ask and /ask/stream.
  Dockerfile
  requirements.txt

index.html                  Your site, with three tags injected before </body>:
                              <link  assets/chatbot.css>
                              <script assets/corpus.js>     ← index first
                              <script assets/chatbot.js>    ← engine second
```

**Load order matters.** `chatbot.js` reads `window.__RAG_CORPUS` at startup and
bails with a console error if `corpus.js` has not run yet.

---

## 3. What happens when someone asks a question

### Default mode: extractive, no server

```
"What drift detection has he done?"
   │
   ├─ gate 0  normalise unicode, strip zero-width chars, cap at 400 chars
   ├─ gate 1  instruction-override and persona-assignment patterns
   ├─ policy  visa / salary / notice period → route to email, stop here
   ├─ tokenise + stem      → [drift, detection, done]
   ├─ expand via synonyms  → + [adwin, distribution, shift]
   ├─ BM25 over all 72 passages, damp repeats from one document
   ├─ gate 2  out-of-domain? vocabulary coverage AND score must both fail
   ├─ gate 3  nothing clears 0.34 confidence → route to him, never improvise
   ├─ compose pick the highest-overlap sentences, quote them verbatim
   └─ gate 5  every citation id must be one that was actually retrieved
```

Total: about 5 ms. Nothing is generated, so nothing can be fabricated.

### Generated mode: prose, needs the service

Retrieval is identical. Only the compose step changes.

```
browser                          backend/app.py                  Groq
───────                          ──────────────                  ────
gates 0–3 exactly as above
        │
        │ POST /ask/stream
        │ { question, contexts[], history[] }
        ▼
                                 build prompt from the
                                 passages the browser sent,
                                 attach the API key
                                          │
                                          │ chat/completions (stream)
                                          ▼
                                                        tokens ──┐
                                          ◄──────────────────────┘
                                 re-emit as SSE `token` events
        ◄─────────────────────────────────┘
render tokens live
        │
        │                        on completion: validate citations
        ◄──── `verdict` event ───┘  ok:true  → keep what was rendered
                                    ok:false → discard, quote sources instead
```

The key never reaches the browser because it is never in the browser. The
browser sends passages it already has and receives text.

---

## 4. The API

Two endpoints. Both accept the same body.

```jsonc
// POST /ask  and  POST /ask/stream
{
  "question": "has he used LLMs?",          // ≤ 400 chars
  "contexts": [                              // ≤ 6, chosen by the browser
    { "id": "llm_chappie", "heading": "Chappie", "text": "..." }
  ],
  "history":  [                              // ≤ 6 turns, for follow-ups
    { "role": "user", "content": "what projects?" },
    { "role": "assistant", "content": "..." }
  ]
}
```

`POST /ask` returns JSON:

```jsonc
{ "answer": "He built ... [[llm_chappie]]." }   // or "NO_EVIDENCE"
```

`POST /ask/stream` returns server-sent events:

```
event: token
data: {"t": "He "}

event: token
data: {"t": "built "}

event: verdict
data: {"ok": true, "answer": "He built ... [[llm_chappie]]."}
```

Tokens stream optimistically. **The `verdict` event is authoritative** and the
client must honour it: `ok:false` means the finished answer cited a passage
that was never retrieved, and the client throws away what it rendered and falls
back to quoting.

`GET /health` returns `{ "ok": true, "model": "..." }`.

### Citation validation runs twice

Once in `backend/app.py` before the verdict is emitted, once in
`chatbot.js` on the rendered HTML. Both compare cited ids against the ids that
were actually sent. Either one failing discards the answer. A single check on
either side would be enough in the happy path; two are there because this is
the gate that stops a fabricated credential reaching a recruiter.

---

## 5. Turning generated answers on

**1. Deploy the service.**

```bash
az containerapp up -n chappie --source backend/ --ingress external \
  --env-vars GROQ_API_KEY=secretref:groq \
             ALLOWED_ORIGIN=https://02-tharuns.github.io \
             GROQ_MODEL=openai/gpt-oss-20b
```

Groq's free tier covers roughly 30 requests a minute and 1,000 a day, which is
far more than a portfolio site sees. Container Apps consumption is free at this
volume and scales to zero.

**2. Point the client at it.** One line in `assets/chatbot.js`:

```js
backendUrl: 'https://chappie.<region>.azurecontainerapps.io/ask',
```

**3. Commit and push.** That is the whole change.

Test locally first, without deploying anything:

```bash
cd backend
GROQ_API_KEY=... uvicorn app:app --port 8000
# then in assets/chatbot.js: backendUrl: 'http://127.0.0.1:8000/ask'
python3 -m http.server 8080
```

### What you get, and what it costs

| | Extractive (default) | Generated |
|---|---|---|
| Reads like | quoted excerpts | prose |
| Follow-up questions | no memory | last 4 turns |
| Infrastructure | none | one container |
| Latency | ~5 ms | ~1 s, streamed |
| Fabrication risk | impossible by construction | possible, caught by the citation gate |
| Works when the service is down | yes | yes, falls back to extractive |

The fallback is the important row. If the container is asleep, rate-limited, or
returns a bad answer, the site keeps working. It just goes back to quoting.

---

## 6. Editing what Chappie knows

```bash
# 1. edit or add a file in content/ — each "## heading" is one passage
# 2. rebuild the index
python3 scripts/build_corpus.py
# 3. check nothing regressed
npm install && npx playwright install chromium
node evals/run_evals.mjs
# 4. commit content/ AND assets/corpus.js together
```

CI fails the build if `assets/corpus.js` is out of date with `content/`, so the
two cannot silently drift apart.

If you change the tokeniser or stemmer in `scripts/build_corpus.py`, you must
make the identical change in `chatbot.js`. They are two implementations of one
function, and when they disagree, query terms stop matching indexed terms and
retrieval degrades quietly rather than failing loudly.
