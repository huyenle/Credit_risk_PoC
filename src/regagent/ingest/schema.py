"""Chunk dataclass and deterministic JSONL serialisation.

A :class:`Chunk` is one citable unit of regulation (a numbered paragraph, or a
whole article/section when it has no numbered paragraphs). ``authority_level``
is derived from ``source`` via :data:`SOURCE_AUTHORITY`, not stored per chunk by
callers.

Determinism (Task 02 Step 7): ``chunk_id`` is a SHA-256 digest of
``(source, ref, text)`` -- never Python's salted ``hash()`` -- and JSONL is
written with sorted keys, ``ensure_ascii=False`` and fixed separators, so two
builds produce byte-identical ``chunks.jsonl``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Authority level per source (set here, once, not per chunk).
SOURCE_AUTHORITY = {
    "CRR": "law",
    "EBA_GL_2017_16": "guideline",
    "ECB_GUIDE": "supervisory_expectation",
    "SR_26_2": "foreign_guidance",
}

# Field order used for JSONL rows (stable, human-friendly).
_FIELD_ORDER = [
    "chunk_id",
    "source",
    "authority_level",
    "ref",
    "article",
    "paragraph",
    "title",
    "page",
    "text",
    "cross_refs",
    "repealed",
]


def compute_chunk_id(source: str, ref: str, text: str) -> str:
    """Stable 16-hex-char id = SHA-256 of ``source\\x00ref\\x00text``."""
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(b"\x00")
    h.update(ref.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()[:16]


@dataclass(frozen=True)
class Chunk:
    """One citable unit of regulation. All text already cleaned and prefixed."""

    chunk_id: str
    source: str
    authority_level: str
    ref: str
    article: str | None
    paragraph: str | None
    title: str | None
    page: int | None
    text: str
    cross_refs: list[str] = field(default_factory=list)
    repealed: bool = False

    @classmethod
    def create(
        cls,
        *,
        source: str,
        ref: str,
        text: str,
        article: str | None = None,
        paragraph: str | None = None,
        title: str | None = None,
        page: int | None = None,
        cross_refs: Iterable[str] | None = None,
        repealed: bool = False,
    ) -> Chunk:
        """Build a Chunk, deriving ``chunk_id`` and ``authority_level``."""
        if source not in SOURCE_AUTHORITY:
            raise ValueError(f"unknown source: {source!r}")
        return cls(
            chunk_id=compute_chunk_id(source, ref, text),
            source=source,
            authority_level=SOURCE_AUTHORITY[source],
            ref=ref,
            article=article,
            paragraph=paragraph,
            title=title,
            page=page,
            text=text,
            cross_refs=list(cross_refs) if cross_refs is not None else [],
            repealed=repealed,
        )

    def to_row(self) -> dict:
        """Ordered dict for JSONL serialisation."""
        d = asdict(self)
        return {k: d[k] for k in _FIELD_ORDER}


def write_jsonl(chunks: Iterable[Chunk], path: Path | str) -> int:
    """Write chunks to ``path`` as deterministic JSONL. Returns the count."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(p, "w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(
                json.dumps(
                    chunk.to_row(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            fh.write("\n")
            n += 1
    return n


def read_jsonl(path: Path | str) -> list[Chunk]:
    """Read chunks written by :func:`write_jsonl`."""
    chunks: list[Chunk] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            chunks.append(Chunk(**{k: d[k] for k in _FIELD_ORDER}))
    return chunks
