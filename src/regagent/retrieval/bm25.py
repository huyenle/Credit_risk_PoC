"""BM25 retrieval over chunk text.

Tokenisation lowercases and keeps digits and parenthesised paragraph numbers, so
a token like ``160(1)`` survives intact (while ``160`` and ``1`` also appear as
their own tokens where present).
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from ..ingest.schema import Chunk

# "160(1)" as one token; otherwise word/number tokens.
_TOKEN = re.compile(r"\d+\([0-9a-z]+\)|[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase tokeniser preserving numbers and parenthesised references."""
    return _TOKEN.findall(text.lower())


class BM25Index:
    """BM25Okapi index over a fixed list of chunks."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._bm25 = BM25Okapi([tokenize(c.text) for c in chunks])

    def search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        """Return the top-``k`` ``(chunk_index, score)`` pairs, best first.

        Ties break by chunk index for deterministic ordering.
        """
        scores = self._bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
        return [(i, float(scores[i])) for i in order[:k]]
