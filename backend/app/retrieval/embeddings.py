"""Dense embedder — fastembed (ONNX runtime), not sentence-transformers.

Why fastembed instead of the sentence-transformers package already present
in this sandbox for other reasons: sentence-transformers pulls in torch,
which alone is several hundred MB installed and pushes runtime memory for
even a tiny model past what Render's free tier (~512MB RAM) gives a whole
process. fastembed runs the same small models (this project uses
`sentence-transformers/all-MiniLM-L6-v2`, which fastembed also ships as an
ONNX export) through onnxruntime instead — tens of MB, no GPU-oriented
runtime baggage — which is the difference between fitting in a free
instance and not.

Behind a tiny Protocol so tests can substitute a deterministic fake without
downloading model weights (this sandbox has no route to huggingface.co; CI
and the deployed service do).
"""

from __future__ import annotations

from typing import Protocol, Sequence


class Embedder(Protocol):
    dim: int

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """Lazy-loaded — the ONNX model is only pulled into memory (and, on
    first run anywhere, downloaded) on first use, so importing this module
    never triggers network access or a slow load."""

    def __init__(self, model_name: str, dim: int):
        self.model_name = model_name
        self.dim = dim
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._load()
        return [v.tolist() for v in model.embed(list(texts))]


class DeterministicFakeEmbedder:
    """Hash-based bag-of-words embedding for tests and for this sandbox,
    where no real embedding model can be downloaded. Not semantically
    meaningful — it exists so the hybrid-retrieval *plumbing* (fusion,
    reranking, the pipeline's orchestration) can be exercised end-to-end
    without a network call, not to validate retrieval quality."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        import hashlib
        import math

        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for word in text.lower().split():
                h = int(hashlib.md5(word.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out
