"""Tokeniser, stemmer, query expansion, and content chunking.

This is a THIRD mirror of the same logic that already lives in two places on
purpose:

    scripts/build_corpus.py    builds assets/corpus.js for the static,
                                browser-only build (GitHub Pages fallback)
    assets/chatbot.js           scores it client-side
    backend/app/textproc.py     this file — scores it server-side, for the
                                FastAPI service's hybrid retrieval pipeline

All three must stay byte-for-byte identical in tokenisation and stemming, or
query terms silently stop matching indexed terms. That already had to be true
across two files before this backend existed; this module does not introduce
the risk, it inherits it. A single shared package importable from all three
runtimes isn't practical here — one is Python offline, one is browser JS, one
is a Python service with a different deployment lifecycle — so the discipline
is: change one, change all three, and let the eval suite (Task in evals/)
catch drift.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "his", "how", "i", "in", "into",
    "is", "it", "its", "of", "on", "or", "our", "that", "the", "their", "then",
    "there", "these", "they", "this", "to", "was", "were", "what", "when",
    "where", "which", "who", "will", "with", "you", "your", "does", "do",
    "did", "can", "could", "would", "should", "about", "any", "all", "also",
    "him", "she", "s", "t",
}

_NONALNUM = re.compile(r"[^a-z0-9]+")


def normalise(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("–", " ").replace("—", " ")
    text = _NONALNUM.sub(" ", text)
    return text


def stem(word: str) -> str:
    """Light suffix stripping. Mirrored byte-for-byte in assets/chatbot.js
    and scripts/build_corpus.py — the trailing-"e" rule is what collapses
    "experienced" and "experience" onto one stem."""
    if len(word) <= 3:
        return word
    for suffix, minimum in (("ies", 4), ("sses", 5), ("ing", 6), ("ed", 5)):
        if word.endswith(suffix) and len(word) >= minimum:
            base = word[: -len(suffix)]
            if suffix == "ies":
                return base + "y"
            if suffix == "sses":
                return base + "ss"
            word = base
            break
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    return word


def tokenise(text: str) -> list[str]:
    return [
        stem(w)
        for w in normalise(text).split()
        if w and len(w) > 1 and w not in STOPWORDS
    ]


# ---------------------------------------------------------------------------
# Query expansion — mirrors assets/chatbot.js EXPANSIONS/AMBIGUOUS verbatim.
# ---------------------------------------------------------------------------

EXPANSIONS: dict[str, list[str]] = {
    "pdm": ["predictive", "maintenance"],
    "cv": ["computer", "vision"],
    "ml": ["machine", "learning"],
    "dl": ["deep", "learning"],
    "nlp": ["natural", "language"],
    "ood": ["out", "distribution", "novelty"],
    "can": ["canalyse", "bus", "controller", "area", "network"],
    "canbus": ["can", "canalyse", "bus"],
    "adas": ["automotive", "perception", "vehicle", "detection", "driver", "assistance"],
    "driver": ["adas", "automotive", "assistance", "vehicle"],
    "assistance": ["adas", "automotive", "driver"],
    "assist": ["adas", "automotive", "driver"],
    "advanced": ["adas", "driver", "assistance"],
    "autonomous": ["adas", "perception", "vehicle", "automotive"],
    "av": ["adas", "autonomous", "vehicle", "perception"],
    "lane": ["calibration", "tracking", "perception", "vehicle"],
    "tracking": ["centroid", "tracking", "perception", "vehicle"],
    "detection": ["yolov5", "detection", "perception", "object"],
    "perception": ["vehicle", "detection", "tracking", "camera", "adas"],
    "automotive": ["vehicle", "adas", "brake", "canalyse", "diagnostic"],
    "vehicle": ["automotive", "adas", "perception", "traffic"],
    "obd": ["can", "canalyse", "diagnostic", "bus"],
    "safety": ["adas", "fault", "diagnostic", "drift"],
    "nvh": ["bsr", "buzz", "squeak", "rattle", "vibration"],
    "bsr": ["buzz", "squeak", "rattle", "nvh", "vibration"],
    "anpr": ["plate", "recognition", "number"],
    "lpr": ["plate", "recognition"],
    "ocr": ["plate", "tesseract", "character"],
    "drift": ["adwin", "distribution", "shift"],
    "rf": ["random", "forest"],
    "cnn": ["convolutional", "neural"],
    "svm": ["one", "class", "novelty"],
    "iot": ["mqtt", "sensor", "edge", "telemetry"],
    "gpa": ["grade", "cgpa"],
    "cgpa": ["gpa", "grade"],
    "uni": ["university"],
    "umd": ["michigan", "dearborn"],
    "masters": ["master", "science", "msc"],
    "bachelors": ["bachelor", "engineering"],
    "degree": ["master", "bachelor", "education", "university"],
    "educational": ["education", "academic", "degree", "qualification"],
    "qualification": ["education", "degree", "academic"],
    "resume": ["profile", "experience", "background"],
    "cv_doc": ["profile", "experience"],
    "job": ["role", "position"],
    "hire": ["role", "open", "contact"],
    "contact": ["email", "linkedin", "github", "reach"],
    "reach": ["email", "contact"],
    "latency": ["millisecond", "inference", "speed"],
    "accuracy": ["percent", "map", "f1", "recall"],
    "paper": ["publication"],
    "publication": ["paper"],
    "robot": ["robotics", "physical"],
    "robotics": ["robot", "physical", "mechatronics"],
    "cloud": ["aws", "azure", "ec2", "docker"],
    "devops": ["docker", "ci", "github", "actions"],
    "hackathon": ["waynehacks", "guardwave"],
    "llm": ["chappie", "retrieval", "generative", "langchain", "transformers"],
    "llms": ["chappie", "retrieval", "generative", "langchain", "transformers"],
    "genai": ["generative", "llm", "chappie", "retrieval"],
    "gen": ["generative", "llm", "chappie"],
    "generative": ["llm", "chappie", "retrieval", "augmented"],
    "gpt": ["llm", "generative", "openai", "chappie"],
    "chatgpt": ["llm", "generative", "openai", "chappie"],
    "openai": ["llm", "generative", "tooling"],
    "anthropic": ["llm", "generative", "tooling"],
    "chatbot": ["chappie", "retrieval", "llm"],
    "rag": ["retrieval", "augmented", "generation", "chappie", "bm25"],
    "retrieval": ["rag", "chappie", "bm25", "augmented"],
    "bm25": ["retrieval", "chappie", "index"],
    "embedding": ["retrieval", "index", "bm25"],
    "embeddings": ["retrieval", "index", "bm25"],
    "transformer": ["hugging", "face", "transformers"],
    "transformers": ["hugging", "face", "langchain"],
    "prompt": ["injection", "guardrail", "chappie"],
    "guardrail": ["gate", "injection", "chappie"],
    "guardrails": ["gate", "injection", "chappie"],
    "opensource": ["open", "source", "github"],
    "stack": ["skill", "framework", "tool", "language"],
    "tech": ["skill", "framework", "tool", "language"],
    "tooling": ["skill", "framework", "tool"],
    "frameworks": ["framework", "skill", "tool"],
    "course": ["coursework", "education"],
    "courses": ["coursework", "education"],
    "coursework": ["course", "education"],
    "strength": ["strong", "skill"],
    "weakness": ["gap", "not", "limited"],
    "gap": ["gaps", "not", "limited"],
    "gaps": ["gap", "not", "limited"],
    # Domain/application vocabulary a recruiter is likely to use when asking
    # "does this transfer to X" — bridges to the domain-fit docs
    # (32/33/34-domain-*.md) added alongside 31-automotive-adas.md.
    "manufacturing": ["industrial", "robotics", "production", "quality", "metrology"],
    "factory": ["manufacturing", "industrial", "production"],
    "production": ["manufacturing", "industrial", "quality"],
    "quality": ["metrology", "statistical", "control", "manufacturing"],
    "metrology": ["quality", "measurement", "manufacturing"],
    "embedded": ["edge", "hardware", "onboard", "raspberry"],
    "onboard": ["edge", "embedded", "hardware"],
    "constrained": ["edge", "embedded", "hardware"],
}

EXPANSION_KEYS = {stem(k) for k in EXPANSIONS}

_CAN_UPPER = re.compile(r"\bCAN\b")
_CAN_NEAR = re.compile(
    r"\b(bus|signal|frame|dbc|obd|decode|decoding|network|vehicle|controller|canalyse)\b",
    re.IGNORECASE,
)


def _expansion_allowed(key: str, raw: str) -> bool:
    """"can" is both the CAN bus and the commonest modal verb in English. Only
    expand it on evidence the visitor meant the acronym: original uppercase,
    or a companion term from the same domain."""
    if key != "can":
        return True
    return bool(_CAN_UPPER.search(raw) or _CAN_NEAR.search(raw))


def expand(tokens: list[str], raw: str) -> list[str]:
    out = list(tokens)
    raw_text = raw or ""
    raw_words = [w for w in normalise(raw_text).split(" ") if w]
    for word in raw_words:
        extra = EXPANSIONS.get(word)
        if extra and _expansion_allowed(word, raw_text):
            out.extend(stem(t) for t in extra)
    for token in tokens:
        extra = EXPANSIONS.get(token)
        if extra and _expansion_allowed(token, raw_text):
            out.extend(stem(t) for t in extra)
    return out


# ---------------------------------------------------------------------------
# Chunking — mirrors scripts/build_corpus.py. Used by backend/ingest.py so the
# service's Qdrant collection and BM25 index are built from the exact same
# content/*.md chunks as the static GitHub Pages fallback.
# ---------------------------------------------------------------------------

HEADING_BOOST = 3
TITLE_BOOST = 2


def parse_front_matter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta: dict[str, str] = {}
    for line in raw[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, raw[end + 4:]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:34]


@dataclass
class Chunk:
    id: str
    doc: str
    section: str
    doc_title: str
    type: str
    domain: str
    date: str
    repo: str
    heading: str
    text: str
    volunteer: bool = True
    triggers: list[str] = field(default_factory=list)
    tf: dict[str, int] = field(default_factory=dict)
    len: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "doc": self.doc, "section": self.section,
            "docTitle": self.doc_title, "type": self.type, "domain": self.domain,
            "date": self.date, "repo": self.repo, "heading": self.heading,
            "text": self.text, "volunteer": self.volunteer, "triggers": self.triggers,
            "tf": self.tf, "len": self.len,
        }

    @staticmethod
    def from_dict(d: dict) -> "Chunk":
        return Chunk(
            id=d["id"], doc=d["doc"], section=d.get("section", ""),
            doc_title=d.get("docTitle", ""), type=d.get("type", ""),
            domain=d.get("domain", ""), date=d.get("date", ""), repo=d.get("repo", ""),
            heading=d.get("heading", ""), text=d.get("text", ""),
            volunteer=d.get("volunteer", True), triggers=d.get("triggers", []),
            tf=d.get("tf", {}), len=d.get("len", 0),
        )


def chunk_markdown(path_stem: str, raw_text: str) -> list[Chunk]:
    meta, body = parse_front_matter(raw_text)
    doc_id = meta.get("id") or path_stem
    chunks: list[Chunk] = []
    for block in re.split(r"^## ", body, flags=re.M)[1:]:
        heading, _, text = block.partition("\n")
        heading = heading.strip()
        text = " ".join(text.split())
        if not text:
            continue
        chunks.append(Chunk(
            id=f"{doc_id}_{slugify(heading)}",
            doc=doc_id,
            section=meta.get("section", ""),
            doc_title=meta.get("title", ""),
            type=meta.get("type", ""),
            domain=meta.get("domain", ""),
            date=meta.get("date", ""),
            repo=meta.get("repo", ""),
            heading=heading,
            text=text,
            volunteer=meta.get("volunteer", "true").lower() != "false",
            triggers=tokenise(meta.get("triggers", "")),
        ))
    return chunks


def compute_bm25_stats(chunks: list[Chunk]) -> tuple[Counter, float]:
    """Fills chunk.tf/chunk.len in place (field-boosted) and returns
    (document_frequency, avgdl) for the corpus."""
    document_frequency: Counter = Counter()
    total_length = 0
    for chunk in chunks:
        boosted = (
            tokenise(chunk.text)
            + tokenise(chunk.heading) * HEADING_BOOST
            + tokenise(chunk.doc_title) * TITLE_BOOST
        )
        counts = Counter(boosted)
        chunk.tf = dict(counts)
        chunk.len = len(boosted)
        total_length += chunk.len
        for term in counts:
            document_frequency[term] += 1
    avgdl = round(total_length / len(chunks), 3) if chunks else 0.0
    return document_frequency, avgdl
