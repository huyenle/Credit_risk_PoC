"""Hybrid retrieval: reciprocal rank fusion of BM25 and dense, plus lookup.

Fusion score is ``Σ 1/(k + rank)`` with ``k = 60`` over the top ``FUSE_DEPTH``
results of each retriever (rank 0-based). An optional ``source`` filter is
applied *before* fusion. The retriever also exposes exact-reference lookup via
:mod:`lookup`.

Public API (per task spec):
    search(query, source=None, k=5) -> list[Chunk]
    get_by_ref(ref) -> list[Chunk]
"""

from __future__ import annotations

from typing import Optional

from ..ingest import build
from ..ingest.schema import Chunk
from ..ingest.scope import ArticleScope, load_scope
from .bm25 import BM25Index
from .dense import DenseIndex
from .lookup import get_by_ref as _get_by_ref

RRF_K = 60
FUSE_DEPTH = 50


def _rrf(ranked: list[int], scores: dict[int, float]) -> None:
    for rank, idx in enumerate(ranked):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (RRF_K + rank)


class Retriever:
    """Hybrid retriever over a chunk corpus (BM25 + dense + exact lookup)."""

    def __init__(
        self,
        chunks: Optional[list[Chunk]] = None,
        model_name: Optional[str] = None,
        scope: Optional[ArticleScope] = None,
    ):
        self.chunks = chunks if chunks is not None else build.build_chunks()
        self._scope = scope or load_scope()
        self._bm25 = BM25Index(self.chunks)
        self._dense = (
            DenseIndex(self.chunks, model_name=model_name)
            if model_name
            else DenseIndex(self.chunks)
        )

    def _candidates(self, source: Optional[str]) -> list[int]:
        if source is None:
            return list(range(len(self.chunks)))
        return [i for i, c in enumerate(self.chunks) if c.source == source]

    def search(
        self, query: str, source: Optional[str] = None, k: int = 5
    ) -> list[Chunk]:
        """Top-``k`` chunks for ``query`` by RRF of BM25 and dense retrievers."""
        allowed = set(self._candidates(source))
        n = len(self.chunks)

        def _filtered(pairs: list[tuple[int, float]]) -> list[int]:
            # Rank the full corpus, keep in-source hits, then take the top depth
            # (source filter applied before fusion, per spec).
            return [i for i, _ in pairs if i in allowed][:FUSE_DEPTH]

        bm = _filtered(self._bm25.search(query, k=n))
        dn = _filtered(self._dense.search(query, k=n))

        fused: dict[int, float] = {}
        _rrf(bm, fused)
        _rrf(dn, fused)

        order = sorted(fused, key=lambda i: (-fused[i], i))
        return [self.chunks[i] for i in order[:k]]

    def get_by_ref(self, ref: str) -> list[Chunk]:
        """Exact reference lookup (delegates to :mod:`lookup`)."""
        return _get_by_ref(self.chunks, ref, scope=self._scope)
