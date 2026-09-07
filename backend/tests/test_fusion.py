from app.retrieval.fusion import fuse_ranked, reciprocal_rank_fusion


def test_rrf_favours_items_ranked_high_in_both_lists():
    bm25 = ["a", "b", "c", "d"]
    dense = ["b", "a", "e", "f"]
    fused = fuse_ranked([bm25, dense], k=60)
    assert fused[0] in ("a", "b")
    assert set(fused[:2]) == {"a", "b"}


def test_rrf_includes_items_present_in_only_one_list():
    fused = fuse_ranked([["a", "b"], ["c"]], k=60)
    assert set(fused) == {"a", "b", "c"}


def test_rrf_scores_are_monotonic_with_rank():
    scores = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
    assert scores["a"] > scores["b"] > scores["c"]


def test_rrf_top_n_truncates():
    fused = fuse_ranked([["a", "b", "c", "d"]], k=60, top_n=2)
    assert fused == ["a", "b"]
