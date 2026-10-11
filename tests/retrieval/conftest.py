"""Shared retrieval fixtures: build the chunk corpus and retriever once."""

from __future__ import annotations

import pytest

from regagent.ingest.build import build_chunks


@pytest.fixture(scope="session")
def corpus():
    """Full parsed chunk corpus (CRR + EBA GL)."""
    return build_chunks()


@pytest.fixture(scope="session")
def retriever(corpus):
    """Hybrid retriever (downloads the embedding model on first run)."""
    from regagent.retrieval.hybrid import Retriever

    return Retriever(chunks=corpus)
