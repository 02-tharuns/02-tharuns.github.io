from app.textproc import chunk_markdown, compute_bm25_stats, normalise, stem, tokenise


def test_stem_collapses_experience_experienced():
    assert stem("experience") == stem("experienced")


def test_stem_short_words_untouched():
    assert stem("cat") == "cat"
    assert stem("cv") == "cv"


def test_tokenise_drops_stopwords_and_punctuation():
    tokens = tokenise("Does he know PyTorch?")
    assert "does" not in tokens  # stopword
    assert "he" not in tokens    # stopword
    assert any(t.startswith("pytorch") or t == "pytorch" for t in tokens)


def test_normalise_handles_smart_quotes_and_dashes():
    # Curly quotes are folded to a straight quote, then the "non-alnum ->
    # space" pass strips that too, same as em/en dashes — matches
    # assets/chatbot.js's normalise() byte-for-byte, including this.
    assert normalise("don’t") == "don t"
    assert "-" not in normalise("state-of-the-art")


def test_chunk_markdown_matches_committed_corpus_size():
    """Regression guard: this must keep matching assets/corpus.js's chunk
    count (76, updated 2026-09-08 when the 4 domain-fit docs — 31-automotive-
    adas.md and 32/33/34-domain-*.md — were simplified from persuasive
    "why this fits" essays into a plain "Exposure" / "Related projects" pair
    of sections each, dropping from 14 combined headings to 8; previously 82,
    updated 2026-09-07 when those same docs and a new automotive/DARE-PM
    cross-reference section were first added (72 before that, per
    ARCHITECTURE.md). Chunk count has stayed at 76 since, but vocabulary has
    moved several times the same week: 988->920 with the domain-fit
    simplification above (briefly 919 with a "Domains worked in" heading,
    before that was renamed to "Exposure" per feedback), then 920->923 when
    content/10-education.md's Bachelor's coursework line grew three
    transcript-verified courses (Computer Integrated Manufacturing, Supply
    Chain and Logistics Management, Operations Research) that tie into the
    domain-fit docs, then 923->929 (2026-09-09) when the word "fit" was
    dropped from the 32/33/34 domain-doc titles and content/62-llm-genai.md
    was rewritten to describe the actual v2 architecture (hybrid BM25 +
    Qdrant dense retrieval + reranking on Render/Vercel/Groq) instead of the
    stale v1 description (browser-only, no server, Azure Container Apps) it
    had carried over — a mismatch means textproc.py has drifted from
    scripts/build_corpus.py's chunker."""
    import pathlib
    content_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "content"
    files = sorted(content_dir.glob("*.md"))
    chunks = []
    for path in files:
        chunks.extend(chunk_markdown(path.stem, path.read_text()))
    assert len(chunks) == 76
    df, avgdl = compute_bm25_stats(chunks)
    assert len(df) == 929
