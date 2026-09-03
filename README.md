# Chappie

*The portfolio RAG.*

Chappie is a retrieval-augmented chatbot over my own CV, projects, education and
skills, running entirely in the visitor's browser on GitHub Pages. No server, no API key,
no cold start.

**Attack success rate 0.0% · False refusal rate 0.0% · 28/28 golden cases correctly sourced · 7/7 deflections safe**
_(69-case suite across four suites, run on every push — see [`evals/`](evals/))_

---

## Why it is built this way

GitHub Pages is static hosting. It cannot run Python, and a key placed in
client-side JavaScript is public to anyone who opens dev tools. So the whole
pipeline runs client-side, and answering is **extractive**: sentences are
selected from the indexed source and quoted, never paraphrased by a generative
model.

That is a deliberate constraint, not a limitation I settled for. A bot speaking
on my behalf that invents a credential is worse than no bot at all — it is a
fabricated claim attached to my name. Extractive answering makes that
**structurally impossible** rather than merely unlikely.

The generative path exists and is one config line away (see below). It is off by
default because the honest version is the better default.

## Pipeline

```
query → 0 hygiene → 1 injection → 2 scope → retrieve → 3 evidence
      → 4 compose → 5 citation integrity → answer
         ↓             ↓            ↓            ↓             ↓
     malformed      blocked     off_topic  not_published  ungrounded
```

| Gate | Does | Cost |
|---|---|---|
| 0 · hygiene | NFKC normalise, strip zero-width and RTL-override characters, length cap | ~0.1 ms |
| 1 · injection | Pattern set for instruction-override and persona-assignment attacks | ~0.2 ms |
| 2 · scope | Out-of-domain detection: vocabulary coverage **and** retrieval score must *both* fail before refusing | ~1 ms |
| — · retrieve | Okapi BM25 over the prebuilt index, with query expansion and same-document damping | ~2 ms |
| 3 · evidence | Nothing clears the score floor → route to him. No "answer from general knowledge" fallback | free |
| 5 · citations | Every cited id must match a chunk that was actually retrieved | ~0.1 ms |

Gate 2 requires **both** signals to fail, which biases toward letting questions
through. That is intentional: a false refusal is visible to a recruiter and reads
as a broken product, while a false accept just falls through to gate 3 and
routes the visitor to him on the honest grounds that the site does not cover it.

## What it says about topics it doesn't know

Absence from a portfolio site is not evidence of absence from a career. So when
a topic isn't in the corpus, the bot states neither direction:

> **Kubernetes** isn't covered in the work published on this site, so I won't
> guess either way. Tharun is open to picking up new tools and domains on top of
> his sensor, edge and evaluation foundation — the accurate answer on whether he
> has touched this comes from him directly.
> *[closest published work, quoted and cited]* · **Ask him directly →**

Three properties, each enforced by the [`deflection`](evals/suites.json) suite on
every push:

- **It never denies.** The site cannot know what isn't on it.
- **It never claims experience.** An invented credential survives exactly until
  the first interview question, which makes it worse than silence.
- **It always routes.** Every deflection opens a pre-filled email, so an
  unanswerable question becomes a conversation rather than a dead end.

Where the query still contains domain terms the corpus knows, it also quotes the
nearest thing actually shipped — the honest version of pivoting to strength.

### Gated passages

Front-matter `volunteer: false` plus a `triggers:` list keeps a passage out of
the candidate pool until the query names one of its trigger terms. Without it a
niche passage bleeds into unrelated answers — a contact question should never
surface anything but contact details.

### The demand log

Every deflected topic is counted in the visitor's browser. Open the console and
run:

```js
__RAG_GAPS()
// [{ topic: "kubernetes", asked: 7, last: "2026-08-27" }, ...]
```

That ranking is a to-do list written by your own audience: the things people
keep asking about that you haven't published yet. Publish the top of the list
and the deflection disappears on its own.

## The corpus is broader than the site

The site showcases eight projects. The corpus indexes **all ten**, including earlier
applied-ML work that no longer earns a place on the front page.

That is deliberate. A recruiter screening for XGBoost, SMOTE, Flask APIs, Parquet
ingestion, clustering or time-series should get a real, cited answer rather than a
routing message — even when the project behind it is two years old and not the work
I lead with. Curate what people see; index everything they might ask about.

## Architecture

[`ARCHITECTURE.md`](ARCHITECTURE.md) walks the whole system: the two runtimes,
the file structure, the request path in both answering modes, the API contract,
and how to switch generated answers on.

## Repository

```
content/            source of truth — plain Markdown with YAML front-matter
scripts/            offline ingestion: chunk → tokenise → BM25 statistics
assets/corpus.js    generated index (62 passages, 59 KB) — commit it
assets/chatbot.js   retrieval, guardrails, extractive composition, UI
evals/              69 cases across four suites + the Playwright harness
backend/            OPTIONAL generated-answer service, /ask and /ask/stream
ARCHITECTURE.md     how it all fits together
```

## Editing the content

The chatbot only knows what is in `content/`. To change what it can say:

```bash
# 1. edit or add a Markdown file in content/
#    every "## heading" becomes one retrievable chunk
# 2. rebuild the index
python3 scripts/build_corpus.py
# 3. check nothing regressed
npm install && npx playwright install chromium
node evals/run_evals.mjs
# 4. commit content/ AND assets/corpus.js together
```

CI fails the build if `assets/corpus.js` is out of date with `content/`, so the
two can never silently drift apart.

Chunking is **structural** — one chunk per `##` heading — rather than a fixed
character window, because a personal corpus is already well organised and a
1,000-character window would cut through the middle of a results paragraph.

## Deploying

1. Push this repository to `<username>.github.io` (or any repo).
2. Settings → Pages → Source: **GitHub Actions**.
3. Push to `main`. The workflow rebuilds the index, runs the eval suite, and
   only deploys if the guardrail metrics hold.

`.nojekyll` is present so Jekyll does not interfere. All asset paths are
relative, so it works on a project page (`user.github.io/repo/`) as well as a
user page.

## Optional: generated answers

When you want prose instead of quotes, deploy [`backend/`](backend/) somewhere
that can run a Docker container, then set one line in `assets/chatbot.js`:

```js
backendUrl: 'https://<your-backend-host>/ask'
```

The browser sends the question and the already-retrieved contexts; the API key
lives on the server and never reaches a visitor. Gate 5 then becomes
load-bearing — it rejects any generated answer citing a chunk that was not
actually retrieved, on both the server and the client.

**Where to run it, free:**

- **Render** (recommended for a first deploy) — no credit card, no CLI.
  Connect the repo in the Render dashboard, point it at `backend/`, it
  auto-detects the `Dockerfile`. 750 free instance-hours/month; a free web
  service spins down after 15 minutes idle and takes about a minute to wake
  on the next request — fine for a portfolio bot, not for a demo you're
  live-clicking through.
- **Azure Container Apps** — no cold start (scales to zero but wakes fast),
  180,000 vCPU-seconds / 360,000 GiB-seconds / 2M requests free per month, but
  needs the `az` CLI and an Azure account:
  ```bash
  az containerapp up -n portfolio-rag --source backend/ --ingress external \
    --env-vars GROQ_API_KEY=secretref:groq ALLOWED_ORIGIN=https://<user>.github.io
  ```

Either way, set these on the host (never in the repo):

| Env var | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | yes | Groq API key. The one place it may live. |
| `ALLOWED_ORIGIN` | yes | Your Pages origin, e.g. `https://<user>.github.io`. CORS rejects everything else. |
| `RATE_LIMIT_PER_MIN`, `RATE_LIMIT_PER_DAY`, `RATE_LIMIT_GLOBAL_PER_DAY` | no | Per-IP and site-wide caps on `/ask`, `/ask/stream`, `/gap` (defaults: 6/min, 40/day/IP, 400/day total). A public endpoint in front of a paid-per-token model needs a ceiling from day one. |
| `GAP_NOTIFY_EMAIL`, `SMTP_USER`, `SMTP_APP_PASSWORD` | no | See below — email yourself when the bot can't answer. Unset any of them and it just logs to stdout instead. |

### Gap notifications

Every time a real visitor asks something the corpus doesn't cover, the browser
posts the question to `/gap`. With mail configured, that becomes an email:

> A visitor asked Chappie something the corpus doesn't cover:
> "Does he have experience with Kubernetes?"
> Detected topic(s): kubernetes

That's the signal for what to add to `content/` next — an actual asked
question, not a guess. Repeats of the same question within 10 minutes are
deduped to one email, and `/gap` shares the same rate limiter as `/ask`.

To wire it up, use a [Gmail App Password](https://myaccount.google.com/apppasswords)
(not your real password) for `SMTP_USER`/`SMTP_APP_PASSWORD`, and set
`GAP_NOTIFY_EMAIL` to wherever you want the reports to land.

## Honest limitations

- **The red-team suite is self-written.** Twelve prompts I thought of myself is
  a smoke test, not a security assessment. You cannot red-team your own system
  into safety.
- **Retrieval is lexical, not semantic.** BM25 with query expansion, chosen
  because it loads instantly and needs no model download. A question phrased
  entirely in vocabulary the corpus never uses will miss. Dense retrieval via
  `transformers.js` is the next upgrade.
- **The injection gate is pattern-based.** The strong version is a classifier
  such as Llama Prompt Guard 2, which needs the backend. Gates 3 and 5 are what
  actually stop an evasion from becoming a fabricated credential.
- **Answers are quotes.** They read as excerpts because they are excerpts. That
  is the trade for guaranteed groundedness.

## Telemetry

Every verdict is logged to `window.__RAG_LOG` with its reason code and score.
Open the console and run `__RAG_LOG` to see the refusal breakdown — that array
is the data behind a refusal-rate panel and, eventually, a drift monitor over
rolling retrieval scores.
