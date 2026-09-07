from app.retrieval.bm25 import BM25Index
from app.textproc import expand, tokenise
from .conftest import CONTENT_DIR
from app.deps import build_bm25_index
from app.config import Settings


def _index(tmp_path) -> BM25Index:
    settings = Settings(content_dir=str(CONTENT_DIR), bm25_corpus_path=str(tmp_path / "c.json"))
    return build_bm25_index(settings)


def test_darepm_query_finds_darepm_chunk(tmp_path):
    idx = _index(tmp_path)
    terms = expand(tokenise("Tell me about DARE-PM"), "Tell me about DARE-PM")
    hits = idx.retrieve(terms)
    assert hits, "expected at least one hit"
    assert hits[0].chunk.doc == "darepm"
    assert 0 <= hits[0].score <= 1


def test_gated_chunk_invisible_without_trigger(tmp_path):
    idx = _index(tmp_path)
    gated = [c for c in idx.chunks if not c.volunteer]
    assert gated, "expected at least one volunteer:false chunk in content/"
    chunk = gated[0]
    # A term set with none of the chunk's triggers must not surface it.
    assert not idx.eligible(chunk, {"totally", "unrelated", "term"})
    # Its own trigger terms must surface it.
    if chunk.triggers:
        assert idx.eligible(chunk, set(chunk.triggers))


def test_save_and_load_round_trip(tmp_path):
    idx = _index(tmp_path)
    path = tmp_path / "roundtrip.json"
    idx.save(path)
    reloaded = BM25Index.load(path)
    assert reloaded.n == idx.n
    assert reloaded.avgdl == idx.avgdl
    assert len(reloaded.chunks) == len(idx.chunks)
