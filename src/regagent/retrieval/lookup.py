"""Exact reference lookup over the chunk corpus (no embeddings).

``get_by_ref("CRR Art. 160")`` returns every paragraph chunk of that article in
order; ``get_by_ref("CRR Art. 160(1)")`` returns just that paragraph. For an
article the scope file marks as repealed, an explicit "repealed" sentinel chunk
is returned instead of an empty list. EBA references
(``EBA GL 2017/16 para 36``) are matched by paragraph.
"""

from __future__ import annotations

import re
from typing import Optional

from ..ingest.scope import ArticleScope, load_scope
from ..ingest.schema import Chunk

_CRR_REF = re.compile(r"CRR Art\.\s*(\d+[a-z]?)(?:\((\w+)\))?$")
_EBA_REF = re.compile(r"EBA GL 2017/16 para\s*(\d+[a-z]?)$")


def _repealed_chunk(article: str) -> Chunk:
    return Chunk.create(
        source="CRR",
        ref=f"CRR Art. {article}",
        text=(
            f"CRR Art. {article} was repealed and is not present in the "
            f"consolidated text (see crr_article_scope.yaml)."
        ),
        article=article,
        repealed=True,
    )


def get_by_ref(
    chunks: list[Chunk],
    ref: str,
    scope: Optional[ArticleScope] = None,
) -> list[Chunk]:
    """Return chunks exactly matching ``ref`` (see module docstring)."""
    ref = ref.strip()

    m = _CRR_REF.match(ref)
    if m:
        article, paragraph = m.group(1), m.group(2)
        scope = scope or load_scope()
        if scope.is_repealed(article):
            return [_repealed_chunk(article)]
        out = [
            c
            for c in chunks
            if c.source == "CRR"
            and c.article == article
            and (paragraph is None or c.paragraph == paragraph)
        ]
        return out

    m = _EBA_REF.match(ref)
    if m:
        paragraph = m.group(1)
        return [
            c
            for c in chunks
            if c.source == "EBA_GL_2017_16" and c.paragraph == paragraph
        ]

    # Fallback: exact ref equality.
    return [c for c in chunks if c.ref == ref]
