#!/usr/bin/env python3
"""Ingestion: content/*.md -> BM25 corpus.json + Qdrant Cloud collection.

Run whenever content/ changes:

    cd backend
    python3 ingest.py                 # embeds + upserts into Qdrant Cloud
    python3 ingest.py --dry-run       # skips Qdrant, just writes corpus.json
                                       # and reports what WOULD be embedded
                                       # (useful with no route to Qdrant Cloud
                                       # or huggingface.co, e.g. a locked-down
                                       # sandbox — see the note at the bottom)

This is the server-side counterpart to scripts/build_corpus.py, which still
builds assets/corpus.js for the static GitHub Pages fallback. Both read the
same content/*.md and share chunking logic (app/textproc.py mirrors
scripts/build_corpus.py's chunker) so the two indexes can never disagree
about what a chunk is, only about how it's scored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import get_settings  # noqa: E402
from app.retrieval.bm25 import BM25Index  # noqa: E402
from app.retrieval.embeddings import DeterministicFakeEmbedder, FastEmbedEmbedder  # noqa: E402
from app.retrieval.vectorstore import InMemoryVectorStore, QdrantVectorStore  # noqa: E402
from app.textproc import chunk_markdown, compute_bm25_stats  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content-dir", default=None, help="Override CONTENT_DIR")
    parser.add_argument("--out", default=None, help="Override BM25_CORPUS_PATH")
    parser.add_argument("--dry-run", action="store_true", help="Skip Qdrant + real embeddings; use fakes and report stats")
    args = parser.parse_args()

    settings = get_settings()
    content_dir = Path(args.content_dir or settings.content_dir)
    out_path = Path(args.out or settings.bm25_corpus_path)

    files = sorted(content_dir.glob("*.md"))
    if not files:
        sys.exit(f"No markdown found in {content_dir}")

    chunks = []
    for path in files:
        chunks.extend(chunk_markdown(path.stem, path.read_text()))

    seen = set()
    for c in chunks:
        if c.id in seen:
            sys.exit(f"Duplicate chunk id: {c.id} — rename a heading.")
        seen.add(c.id)

    df, avgdl = compute_bm25_stats(chunks)
    bm25 = BM25Index(chunks=chunks, df=df, avgdl=avgdl)
    bm25.save(out_path)
    print(f"  files      {len(files)}")
    print(f"  chunks     {len(chunks)}")
    print(f"  vocabulary {len(df)}")
    print(f"  avg length {avgdl}")
    print(f"  written    {out_path}  ({out_path.stat().st_size / 1024:.0f} KB)")

    if args.dry_run:
        embedder = DeterministicFakeEmbedder(dim=settings.embedding_dim)
        store = InMemoryVectorStore(dim=settings.embedding_dim)
        print("  [dry-run] using a deterministic fake embedder + in-memory vector store")
    else:
        embedder = FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim)
        store = QdrantVectorStore(settings.qdrant_url, settings.qdrant_api_key, settings.qdrant_collection, settings.embedding_dim)
        store.ensure_collection()

    texts = [f"{c.heading}. {c.text}" for c in chunks]
    vectors = embedder.encode(texts)
    payloads = [{"doc": c.doc, "heading": c.heading, "section": c.section} for c in chunks]
    store.upsert([c.id for c in chunks], vectors, payloads)
    print(f"  embedded   {len(chunks)} chunks -> {'in-memory store' if args.dry_run else settings.qdrant_collection}")

    if not args.dry_run:
        print(f"  qdrant count now: {store.count()}")


if __name__ == "__main__":
    main()
