"""Tests for dense + hybrid retrieval (downloads the embedding model once)."""

from __future__ import annotations

import pytest


def test_source_filter_returns_only_that_source(retriever):
    hits = retriever.search("PD floor corporate", source="CRR", k=5)
    assert hits
    assert all(c.source == "CRR" for c in hits)


def test_hybrid_finds_pd_floor_article(retriever):
    hits = retriever.search("minimum PD input floor for corporate exposures", k=5)
    assert any(c.article == "160" for c in hits)


def test_get_by_ref_delegates(retriever):
    out = retriever.get_by_ref("CRR Art. 160(1)")
    assert len(out) == 1 and out[0].paragraph == "1"
    assert retriever.get_by_ref("CRR Art. 155")[0].repealed is True


def test_search_is_deterministic(retriever):
    a = retriever.search("loss given default downturn", k=5)
    b = retriever.search("loss given default downturn", k=5)
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]


def test_dense_index_standalone(corpus):
    from regagent.retrieval.dense import DenseIndex

    idx = DenseIndex(corpus)
    hits = idx.search("probability of default estimation", k=5)
    assert len(hits) == 5
    assert all(-1.01 <= s <= 1.01 for _, s in hits)  # cosine range
