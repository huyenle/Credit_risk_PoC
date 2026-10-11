"""Extract and normalise CRR cross-references from provision text.

Recognises forms such as ``Article 153``, ``Article 160(1)``,
``Articles 161 to 163`` (range, expanded), ``Articles 161 and 162``, and
``point (a) of Article 164(4)``. All are normalised to ``CRR Art. N`` or
``CRR Art. N(p)``; ranges expand to the individual articles. The returned list
is de-duplicated and sorted deterministically (so ``chunks.jsonl`` is stable).
"""

from __future__ import annotations

import re

# "160", "159a", "142a" — number with an optional lowercase insertion letter.
_ARTNUM = r"\d+[a-z]?"

# A single article reference with an optional paragraph, e.g. "Article 164(4)".
# The negative lookahead stops it firing on the "Article" inside "Articles".
_SINGLE = re.compile(rf"Article\s+({_ARTNUM})(?:\((\d+[a-z]?)\))?")
# A range, e.g. "Articles 161 to 163" (letters ignored for expansion).
_RANGE = re.compile(r"Articles\s+(\d+)\s+to\s+(\d+)")
# A plural list body after "Articles", e.g. "161 and 162", "153 and 157, and".
_PLURAL = re.compile(rf"Articles\s+((?:{_ARTNUM}|\s|,|and|to)+)")
_ARTNUM_RE = re.compile(_ARTNUM)


def _fmt(article: str, paragraph: str | None = None) -> str:
    return f"CRR Art. {article}" + (f"({paragraph})" if paragraph else "")


def _sort_key(ref: str) -> tuple:
    m = re.match(r"CRR Art\. (\d+)([a-z]?)(?:\((\w+)\))?", ref)
    if not m:
        return (10**9, "", "")
    num, letter, para = m.group(1), m.group(2), m.group(3) or ""
    return (int(num), letter, para)


def extract_crossrefs(text: str, exclude: str | None = None) -> list[str]:
    """Return normalised, de-duplicated, sorted cross-references in ``text``.

    ``exclude`` (e.g. a chunk's own ``ref``) is dropped so a provision never
    cites itself.
    """
    refs: set[str] = set()

    for lo, hi in _RANGE.findall(text):
        lo_i, hi_i = int(lo), int(hi)
        if hi_i >= lo_i and hi_i - lo_i <= 100:
            for n in range(lo_i, hi_i + 1):
                refs.add(_fmt(str(n)))

    # Plural list bodies ("Articles 153 and 157, ...") -> each listed article.
    # Endpoints of any "to" range are added here; interior members via _RANGE.
    for body in _PLURAL.findall(text):
        for num in _ARTNUM_RE.findall(body):
            refs.add(_fmt(num))

    for article, paragraph in _SINGLE.findall(text):
        refs.add(_fmt(article, paragraph or None))

    if exclude is not None:
        refs.discard(exclude)
    return sorted(refs, key=_sort_key)
