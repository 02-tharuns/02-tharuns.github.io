"""Dense vector store — Qdrant Cloud in production, an in-memory cosine
index for tests/local dev where Qdrant Cloud isn't reachable (this sandbox
has no route to cloud.qdrant.io; CI and the deployed service do).
"""

from __future__ import annotations

import math
from typing import Protocol


class VectorStore(Protocol):
    def upsert(self, ids: list[str], vectors: list[list[float]], payloads: list[dict]) -> None: ...
    def search(self, query_vector: list[float], top_n: int) -> list[tuple[str, float]]: ...
    def count(self) -> int: ...


class QdrantVectorStore:
    def __init__(self, url: str, api_key: str, collection: str, dim: int):
        self.url = url
        self.api_key = api_key
        self.collection = collection
        self.dim = dim
        self._client = None

    def _load(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self.url, api_key=self.api_key)
        return self._client

    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams
        client = self._load()
        existing = {c.name for c in client.get_collections().collections}
        if self.collection not in existing:
            client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )

    def upsert(self, ids: list[str], vectors: list[list[float]], payloads: list[dict]) -> None:
        from qdrant_client.models import PointStruct
        client = self._load()
        # Qdrant point ids must be uint64 or UUID — our chunk ids are slugs,
        # so payload carries the real id and the point id is its stable hash.
        points = [
            PointStruct(id=_stable_point_id(cid), vector=vec, payload={**payload, "chunk_id": cid})
            for cid, vec, payload in zip(ids, vectors, payloads)
        ]
        client.upsert(collection_name=self.collection, points=points)

    def search(self, query_vector: list[float], top_n: int) -> list[tuple[str, float]]:
        client = self._load()
        results = client.query_points(
            collection_name=self.collection, query=query_vector, limit=top_n
        ).points
        return [(r.payload["chunk_id"], float(r.score)) for r in results]

    def count(self) -> int:
        client = self._load()
        return client.count(collection_name=self.collection).count


def _stable_point_id(chunk_id: str) -> int:
    import hashlib
    return int(hashlib.md5(chunk_id.encode()).hexdigest()[:16], 16)


class InMemoryVectorStore:
    """Cosine-similarity search over vectors held in a plain dict. Used for
    local dev and tests; also serves as the pipeline's degrade-gracefully
    path if Qdrant Cloud is unreachable at request time (see pipeline.py)."""

    def __init__(self, dim: int):
        self.dim = dim
        self._vectors: dict[str, list[float]] = {}

    def upsert(self, ids: list[str], vectors: list[list[float]], payloads: list[dict]) -> None:
        for cid, vec in zip(ids, vectors):
            self._vectors[cid] = vec

    def search(self, query_vector: list[float], top_n: int) -> list[tuple[str, float]]:
        scored = [(cid, _cosine(query_vector, vec)) for cid, vec in self._vectors.items()]
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:top_n]

    def count(self) -> int:
        return len(self._vectors)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
