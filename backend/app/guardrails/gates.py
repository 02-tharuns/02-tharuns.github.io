"""The six gates and the extractive/deflection composition logic, ported
from assets/chatbot.js. See that file's header comment for the pipeline
order; `ask/routes.py` reproduces the same order calling into this class.

Two things changed on the way from browser to server, both noted inline:
  1. Retrieval is now hybrid (BM25 + dense + rerank) via RetrievalPipeline,
     not pure BM25 — gates.py only cares about the resulting Hit.score,
     which stays on the same calibrated 0..1 scale (see retrieval/pipeline.py).
  2. Everything here is synchronous CPU-bound Python; the async boundary is
     one level up in ask/routes.py.
"""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass

from ..retrieval.bm25 import BM25Index
from ..retrieval.pipeline import Hit, RetrievalPipeline
from ..textproc import STOPWORDS, expand, stem, tokenise
from . import patterns as pat

TOP_K = 3
EVIDENCE_FLOOR = 0.34
SCOPE_COVERAGE_FLOOR = 0.34
SCOPE_SCORE_FLOOR = 0.22
SAME_DOC_PENALTY = 0.72
MAX_CHARS = 400
MIN_CHARS = 2
PIVOT_EXCLUDED_SECTIONS = {"contact", "about"}


@dataclass
class Rejection:
    code: str
    detail: str = ""


def escape_html(value: str) -> str:
    return html_module.escape(str(value), quote=True)


_SENTINEL = "\u0000"
_INNER_DOT = re.compile(r"(\w)\.(\w)")
_SENTENCE_SPLIT = re.compile(r"[^.!?]+[.!?]+(?:\s|$)")


def sentences(text: str) -> list[str]:
    """Periods inside emails/decimals/version numbers aren't sentence ends."""
    guarded = _INNER_DOT.sub(lambda m: f"{m.group(1)}{_SENTINEL}{m.group(2)}", text)
    parts = _SENTENCE_SPLIT.findall(guarded) or [guarded]
    return [p.replace(_SENTINEL, ".") for p in parts]


class GuardrailEngine:
    def __init__(self, bm25: BM25Index, pipeline: RetrievalPipeline, owner: str, contact_email: str, bot_name: str = "Chappie"):
        self.bm25 = bm25
        self.pipeline = pipeline
        self.owner = owner
        self.contact_email = contact_email
        self.bot_name = bot_name

    def is_known_term(self, term: str) -> bool:
        return term in self.bm25.vocab or term in _expansion_keys()

    # --- gate 0 ---------------------------------------------------------------

    def sanitise(self, raw: str) -> tuple[str, Rejection | None]:
        cleaned = pat.INVISIBLE.sub("", str(raw or ""))
        cleaned = _nfkc(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) < MIN_CHARS or len(cleaned) > MAX_CHARS:
            return cleaned, Rejection("malformed", f"length {len(cleaned)}")
        return cleaned, None

    # --- gate 1 ---------------------------------------------------------------

    def check_injection(self, text: str) -> Rejection | None:
        for pattern in pat.INJECTION:
            if pattern.search(text):
                return Rejection("injection", pattern.pattern[:40])
        return None

    def check_task_request(self, text: str) -> Rejection | None:
        return Rejection("off_topic", "task request") if pat.TASK_REQUEST.search(text) else None

    def check_route(self, text: str) -> Rejection | None:
        return Rejection("route", "policy question") if pat.ROUTE.search(text) else None

    def check_personal(self, text: str) -> Rejection | None:
        if pat.PERSONAL.search(text) and not pat.PERSONAL_CARVEOUT.search(text):
            return Rejection("out_of_bounds", "personal detail")
        return None

    # --- gate 2 -----------------------------------------------------------------

    def check_scope(self, tokens: list[str], hits: list[Hit]) -> Rejection | None:
        if not tokens:
            return Rejection("off_topic", "no content terms")
        known = sum(1 for t in tokens if t in self.bm25.vocab)
        coverage = known / len(tokens)
        best = hits[0].score if hits else 0.0
        if coverage < SCOPE_COVERAGE_FLOOR and best < SCOPE_SCORE_FLOOR:
            return Rejection("off_topic", f"coverage {coverage:.2f}")
        return None

    # --- gate 3 -----------------------------------------------------------------

    def check_evidence(self, hits: list[Hit]) -> tuple[list[Hit], Rejection | None]:
        strong = [h for h in hits if h.score >= EVIDENCE_FLOOR]
        if not strong:
            best = f"{hits[0].score:.3f}" if hits else "0"
            return [], Rejection("no_evidence", best)
        return strong[:TOP_K], None

    # --- gate 5 -----------------------------------------------------------------

    def validate_citations(self, answer_html: str, allowed_ids: set[str]) -> Rejection | None:
        cited = re.findall(r'data-cite="([^"]+)"', answer_html)
        if not cited:
            return Rejection("ungrounded", "no citations emitted")
        ghosts = [c for c in cited if c not in allowed_ids]
        if ghosts:
            return Rejection("ungrounded", f"fabricated ids: {', '.join(ghosts)}")
        return None

    # --- subject / unknown-topic analysis ----------------------------------------

    def candidate_skill_terms(self, tokens: list[str]) -> list[str]:
        return [t for t in tokens if t not in pat.FRAME_WORDS and t not in STOPWORDS and not t.isdigit()]

    def unknown_terms(self, raw_text: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        acronyms = {w.lower() for w in re.findall(r"\b[A-Z]{2,6}\b", raw_text)}
        from ..textproc import normalise
        for word in normalise(raw_text).split(" "):
            if not word:
                continue
            is_acronym = word in acronyms
            if (len(word) < 4 and not is_acronym) or word in STOPWORDS or word.isdigit():
                continue
            stemmed = stem(word)
            if stemmed in pat.FRAME_WORDS or self.is_known_term(stemmed) or stemmed in seen:
                continue
            seen.add(stemmed)
            out.append(word)
        return out[:2]

    def nearest_strength(self, tokens: list[str], raw_text: str) -> Hit | None:
        known = [t for t in tokens if self.is_known_term(t) and t not in pat.FRAME_WORDS]
        if not known:
            return None
        # Mirrors the browser's `retrieve(expand(known, rawText))` exactly:
        # BM25-only, re-scored on the narrowed known-term subject rather than
        # the full question, and never the hybrid pipeline (dense retrieval
        # over a *deliberately incomplete* query would just reintroduce the
        # unknown topic through semantic similarity).
        terms = expand(known, raw_text)
        bm25_hits = self.bm25.retrieve(terms, candidates=self.pipeline.bm25_top_n)
        candidates = [h for h in bm25_hits if h.chunk.section not in PIVOT_EXCLUDED_SECTIONS]
        if candidates and candidates[0].score >= 0.20:
            top = candidates[0]
            return Hit(chunk=top.chunk, score=top.score, bm25_raw=top.raw, source="bm25")
        return None

    # --- extractive composition ---------------------------------------------------

    def best_excerpt(self, chunk, terms: list[str], limit: int = 360) -> str:
        wanted = set(terms)
        ranked = []
        for index, sentence in enumerate(sentences(chunk.text)):
            words = tokenise(sentence)
            overlap = sum(1 for w in words if w in wanted)
            score = overlap / (len(words) ** 0.5 if words else 1)
            ranked.append((score, index, sentence.strip()))
        ranked.sort(key=lambda r: (-r[0], r[1]))
        picked = []
        length = 0
        for score, index, sentence in ranked:
            if length + len(sentence) > limit and picked:
                break
            picked.append((index, sentence))
            length += len(sentence)
            if len(picked) >= 3:
                break
        picked.sort(key=lambda p: p[0])
        return " ".join(s for _, s in picked)

    def lead(self, intent: str) -> str:
        if intent == "skill":
            return "From his documents:"
        if intent == "metric":
            return "The measured figures on record:"
        if intent == "contact":
            return "Here are his details:"
        if intent == "fit":
            return "Here is what his documents say about his background and focus:"
        return "From his documents:"

    def source_card(self, hits: list[Hit], terms: list[str], numbered: bool = False, snippet_len: int = 170) -> str:
        rows = []
        for i, hit in enumerate(hits):
            snippet = self.best_excerpt(hit.chunk, terms, snippet_len)
            badge = f'<span class="rag-src-n">{i + 1}</span>' if numbered else ""
            domain_html = f'<p class="rag-src-domain">{escape_html(hit.chunk.domain)}</p>' if hit.chunk.domain else ""
            rows.append(
                f'<div class="rag-source-row">{badge}'
                f'<div class="rag-src-body">'
                f'<p class="rag-src-heading">{escape_html(hit.chunk.heading)} '
                f'<button type="button" class="rag-cite rag-src-id" data-cite="{escape_html(hit.chunk.id)}" '
                f'data-section="{escape_html(hit.chunk.section)}" '
                f'title="Open the source section on this page">{escape_html(hit.chunk.doc)}</button>'
                f'{self.repo_link_html(hit.chunk.repo)}</p>'
                f'{domain_html}'
                f'<p class="rag-src-snippet">{escape_html(snippet)}</p>'
                f'</div></div>'
            )
        return f'<div class="rag-sources">{"".join(rows)}</div>'

    def repo_link_html(self, repo_url: str) -> str:
        """A cited project with a known GitHub repo gets a real hyperlink to
        it, not just the in-page scroll the citation button already gives —
        a recruiter reading a citation should be able to reach the actual
        code, not only the portfolio prose about it. Empty when the content
        file's front-matter has no `repo:` (most non-project sections, and a
        few project files that haven't had their repo URL added yet — see
        content/*.md's `repo:` field, never guessed or fabricated here)."""
        if not repo_url:
            return ""
        return (
            f' <a class="rag-repo-link" href="{escape_html(repo_url)}" '
            f'target="_blank" rel="noopener noreferrer" title="Open the GitHub repository">GitHub ↗</a>'
        )

    def compose(self, intent: str, hits: list[Hit], terms: list[str]) -> str:
        return f'<p class="rag-lead">{escape_html(self.lead(intent))}</p>' + self.source_card(hits, terms)

    def render_citations(self, answer: str, hits: list[Hit]) -> str:
        """Generated-answer path: [[chunk_id]] markers -> numbered superscripts
        + a trailing source card, so extractive and generated answers cite
        through the same visual object."""
        order: list[str] = []
        seen: set[str] = set()

        def repl(m: re.Match) -> str:
            cid = m.group(1)
            if cid not in seen:
                seen.add(cid)
                order.append(cid)
            return f'<sup class="rag-ref" data-cite="{escape_html(cid)}">{order.index(cid) + 1}</sup>'

        body = re.sub(r"\[\[([a-z0-9_\-]+)\]\]", repl, escape_html(answer), flags=re.I)
        by_id = {h.chunk.id: h for h in hits}
        cited_hits = [by_id[cid] for cid in order if cid in by_id]
        if not cited_hits:
            return f"<p>{body}</p>"
        return f"<p>{body}</p>" + self.source_card(cited_hits, [], numbered=True, snippet_len=170)

    # --- deflection ("not published") path -----------------------------------------

    def compose_deflection(self, topics: list[str], adjacent: Hit | None, terms: list[str]) -> str:
        named = ", ".join(topics)
        subject = f"<strong>{escape_html(named[0].upper() + named[1:])}</strong>" if topics else "That"
        parts = [
            f"<p>{subject} isn't covered in the work published on this site, so I won't "
            f"guess either way. {escape_html(self.owner)} is open to picking up new tools and domains "
            f"on top of his sensor, edge and evaluation foundation. The accurate answer on whether he "
            f"has touched this comes from him directly.</p>"
        ]
        if adjacent:
            excerpt = self.best_excerpt(adjacent.chunk, terms, 260)
            parts.append('<p class="rag-lead">The closest published work:</p>')
            parts.append(
                f'<blockquote class="rag-quote">{escape_html(excerpt)}'
                f'<button type="button" class="rag-cite" data-cite="{escape_html(adjacent.chunk.id)}" '
                f'data-section="{escape_html(adjacent.chunk.section)}">{escape_html(adjacent.chunk.heading)}</button>'
                f'{self.repo_link_html(adjacent.chunk.repo)}'
                f'</blockquote>'
            )
        import urllib.parse
        subject_line = urllib.parse.quote("Question about " + (", ".join(topics) or "your experience"))
        parts.append(
            f'<p><a class="rag-mail" href="mailto:{self.contact_email}?subject={subject_line}">'
            f"Ask him directly →</a></p>"
        )
        return "".join(parts)

    # --- refusal copy -------------------------------------------------------------

    def refusal_html(self, code: str) -> str:
        table = {
            "malformed": lambda: f"<p>That was either empty or longer than I accept ({MAX_CHARS} characters). Try a shorter question.</p>",
            "injection": lambda: f"<p>That looks like an attempt to rewrite my instructions, so I logged it and skipped it. Happy to take a real question about {escape_html(self.owner)}'s work.</p>",
            "off_topic": lambda: f'<p>That one is outside what I know. I only cover {escape_html(self.owner)}\'s background, projects, skills and education. Try <em>"What has he built with sensor data?"</em></p>',
            "no_evidence": lambda: f'<p>That isn\'t covered in the work published here. <a class="rag-mail" href="mailto:{self.contact_email}">Ask him directly →</a></p>',
            "not_published": lambda: "",
            "out_of_bounds": lambda: f'<p>Personal contact details beyond his professional links aren\'t indexed. You can reach him at <a href="mailto:{self.contact_email}">{self.contact_email}</a>.</p>',
            "route": lambda: f'<p>Work authorisation, compensation, notice period, and start dates are best answered by {escape_html(self.owner)} directly rather than by me — a stale answer here would be worse than none. <a href="mailto:{self.contact_email}">{self.contact_email}</a></p>',
            "ungrounded": lambda: "<p>I drafted an answer I couldn't verify against the sources, so I'm not showing it. Try asking more specifically.</p>",
            "backend_error": lambda: "<p>The answering service didn't respond, so I'm showing the retrieved sources instead.</p>",
        }
        return table.get(code, table["no_evidence"])()


_EXPANSION_KEYS_CACHE = None


def _expansion_keys():
    global _EXPANSION_KEYS_CACHE
    if _EXPANSION_KEYS_CACHE is None:
        from ..textproc import EXPANSION_KEYS
        _EXPANSION_KEYS_CACHE = EXPANSION_KEYS
    return _EXPANSION_KEYS_CACHE


def _nfkc(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", text)


def classify_intent(text: str) -> str:
    if pat.SKILL_QUESTION.search(text) and not pat.OPEN_QUESTION.search(text):
        return "skill"
    if re.search(r"\b(accuracy|latency|percent|map|f1|recall|how\s+many|how\s+much|gpa|score)\b", text, re.I):
        return "metric"
    if re.search(r"\b(email|contact|reach|linkedin|github|hire|available)\b", text, re.I):
        return "contact"
    return "general"
