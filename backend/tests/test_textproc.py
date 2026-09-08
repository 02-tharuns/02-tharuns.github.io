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
    count (82, updated 2026-09-07 when the domain-fit docs — 32/33/34-domain-
    *.md — and a new automotive/DARE-PM cross-reference section were added;
    previously 72, per ARCHITECTURE.md; vocabulary bumped 987->988 the same
    day when a "Robotics Laboratory" reference was corrected to "CNC and
    Robotics Laboratory" against the actual transcript, adding "cnc" as a
    term) — a mismatch means textproc.py has drifted from
    scripts/build_corpus.py's chunker."""
    import pathlib
    content_dir = pathlib.Path(__file__).resolve().parent.parent.parent / "content"
    files = sorted(content_dir.glob("*.md"))
    chunks = []
    for path in files:
        chunks.extend(chunk_markdown(path.stem, path.read_text()))
    assert len(chunks) == 82
    df, avgdl = compute_bm25_stats(chunks)
    assert len(df) == 988
