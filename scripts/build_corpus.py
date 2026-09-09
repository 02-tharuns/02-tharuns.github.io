#!/usr/bin/env python3
"""
Offline ingestion pipeline for the portfolio RAG.

  content/*.md  ->  chunk  ->  tokenise  ->  BM25 statistics  ->  assets/corpus.js

Run this whenever you edit anything in content/, then commit the generated file:

    python3 scripts/build_corpus.py

Design notes
------------
* Chunking is STRUCTURAL. Every level-2 heading ("## ...") becomes one chunk.
  Fixed-width character windows would cut through the middle of a project's
  results paragraph; a personal corpus is already well structured, so use it.

* The tokeniser and stemmer here are mirrored EXACTLY in assets/chatbot.js.
  If you change one you must change the other, or query terms will stop
  matching indexed terms and retrieval will silently degrade. There is a
  parity test in evals/run_evals.py that will catch it.

* Heading terms are injected into the term counts three times and the document
  title twice. This is field boosting done at build time so the browser does
  not have to carry a multi-field scorer.
"""

import json
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
OUT = ROOT / "assets" / "corpus.js"

HEADING_BOOST = 3
TITLE_BOOST = 2

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "his", "how", "i", "in", "into",
    "is", "it", "its", "of", "on", "or", "our", "that", "the", "their", "then",
    "there", "these", "they", "this", "to", "was", "were", "what", "when",
    "where", "which", "who", "will", "with", "you", "your", "does", "do",
    "did", "can", "could", "would", "should", "about", "any", "all", "also",
    "him", "she", "s", "t",
}


# --------------------------------------------------------------------------
# Tokenisation  (MIRRORED IN assets/chatbot.js — keep the two identical)
# --------------------------------------------------------------------------

def normalise(text: str) -> str:
    text = text.lower()
    text = text.replace("’", "'").replace("‘", "'")
    text = text.replace("–", " ").replace("—", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text


def stem(word: str) -> str:
    """Light suffix stripping. Mirrored byte-for-byte in assets/chatbot.js.

    The trailing-"e" rule is what makes "experienced" and "experience" collapse
    to the same stem. Without it the two never match, a skill question phrased
    with "experienced" looks like an unknown subject, and a perfectly good
    question gets deflected.
    """
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


def tokenise(text: str):
    return [
        stem(w)
        for w in normalise(text).split()
        if w and w not in STOPWORDS and len(w) > 1
    ]


# --------------------------------------------------------------------------
# Parsing and chunking
# --------------------------------------------------------------------------

def parse_front_matter(raw: str):
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    meta = {}
    for line in raw[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, raw[end + 4 :]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:34]


_DISPLAY_OVERRIDE_RE = re.compile(r"<!--\s*display:.*?-->", re.DOTALL)


def chunk_file(path: pathlib.Path):
    """Mirrors backend/app/textproc.py's chunk_markdown, including stripping
    a `<!-- display: ... -->` first-person override (see that file's
    docstring) — v1's chatbot.js answers purely by quoting indexed text
    verbatim, so leaking first-person prose into this corpus would be worse
    here than anywhere else in the codebase."""
    meta, body = parse_front_matter(path.read_text())
    doc_id = meta.get("id") or path.stem
    chunks = []
    for block in re.split(r"^## ", body, flags=re.M)[1:]:
        heading, _, text = block.partition("\n")
        heading = heading.strip()
        text = _DISPLAY_OVERRIDE_RE.sub("", text)
        text = " ".join(text.split())
        if not text:
            continue
        chunks.append(
            {
                "id": f"{doc_id}_{slugify(heading)}",
                "doc": doc_id,
                "section": meta.get("section", ""),
                "docTitle": meta.get("title", ""),
                "type": meta.get("type", ""),
                # Free-text, comma-separated (e.g. "automotive, industrial").
                # Purely a display label on the source card right now — not
                # consulted by retrieval or the gates, so a missing or wrong
                # tag can't change what Chappie answers.
                "domain": meta.get("domain", ""),
                "date": meta.get("date", ""),
                "repo": meta.get("repo", ""),
                "heading": heading,
                "text": text,
                # Gated chunks never enter the candidate pool on their own. They
                # surface only when the query hits one of their trigger terms.
                # Without this, a niche passage bleeds into unrelated answers —
                # a contact question should never pull up anything else.
                "volunteer": meta.get("volunteer", "true").lower() != "false",
                "triggers": tokenise(meta.get("triggers", "")),
            }
        )
    return chunks


# --------------------------------------------------------------------------
# Index construction
# --------------------------------------------------------------------------

def build():
    files = sorted(CONTENT.glob("*.md"))
    if not files:
        sys.exit(f"No markdown found in {CONTENT}")

    chunks = []
    for path in files:
        chunks.extend(chunk_file(path))

    seen = set()
    for chunk in chunks:
        if chunk["id"] in seen:
            sys.exit(f"Duplicate chunk id: {chunk['id']} — rename a heading.")
        seen.add(chunk["id"])

    document_frequency = Counter()
    total_length = 0

    for chunk in chunks:
        boosted = (
            tokenise(chunk["text"])
            + tokenise(chunk["heading"]) * HEADING_BOOST
            + tokenise(chunk["docTitle"]) * TITLE_BOOST
        )
        counts = Counter(boosted)
        chunk["tf"] = dict(counts)
        chunk["len"] = len(boosted)
        total_length += chunk["len"]
        for term in counts:
            document_frequency[term] += 1

    index = {
        "version": 2,
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "N": len(chunks),
        "avgdl": round(total_length / len(chunks), 3),
        "df": dict(sorted(document_frequency.items())),
        "chunks": chunks,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(
        "/* Generated by scripts/build_corpus.py — do not edit by hand. */\n"
        "window.__RAG_CORPUS = " + payload + ";\n"
    )

    print(f"  files      {len(files)}")
    print(f"  chunks     {len(chunks)}")
    print(f"  vocabulary {len(document_frequency)}")
    print(f"  avg length {index['avgdl']}")
    print(f"  written    {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    build()
