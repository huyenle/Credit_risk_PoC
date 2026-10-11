"""Parse EBA/GL/2017/16 (PD/LGD estimation) PDF into chunks.

The guidelines number their paragraphs sequentially (1..N). This parser reads
only the guidelines section (§3 onward in the document, where numbering starts),
skips the cover, table of contents and the "Compliance and reporting
obligations" boilerplate (section 1), and chunks by numbered paragraph. The
enclosing numbered section heading becomes the chunk ``title`` and the page the
paragraph starts on is recorded.

Repeated page headers (the running title) and standalone page numbers are
stripped. Unnumbered material following a paragraph (e.g. the definitions table
after para 8) stays attached to that paragraph's chunk.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pymupdf

from . import loader
from .crossrefs import extract_crossrefs
from .schema import Chunk

SOURCE = "EBA_GL_2017_16"
DEFAULT_PDF = loader.REGULATIONS_DIR / "EBA_GL_2017_16.pdf"

# Running header on every page, and the section where numbered guidelines begin.
_HEADER = "GUIDELINES ON PD ESTIMATION, LGD ESTIMATION AND TREATMENT DEFAULTED EXPOSURES"
_START_HEADING = "Compliance and reporting obligations"
_END_HEADING = "Accompanying documents"

# A paragraph may begin inline ("36. Text...") or with the number on its own
# line ("36." then the text on following lines).
_PARA_INLINE = re.compile(r"^(\d+)\.\s+\S.*$")
_PARA_ALONE = re.compile(r"^(\d+)\.$")
_HEADING = re.compile(r"^(\d+)(?:\.\d+)*\s+[A-Z].*$")
_PAGENUM = re.compile(r"^\d+$")
_WS = re.compile(r"\s+")

# Top-level section number of the boilerplate to skip (its heading matches
# _START_HEADING); everything from the next top-level section on is kept.
_SKIP_SECTION = 1


def _page_lines(page: "pymupdf.Page") -> list[str]:
    """Non-empty lines of a page with the running header and page number removed."""
    out: list[str] = []
    for raw in page.get_text().splitlines():
        s = raw.strip()
        if not s or s == _HEADER:
            continue
        if not out and _PAGENUM.match(s):  # leading page-number line
            continue
        out.append(s)
    return out


def _find_window(doc: "pymupdf.Document") -> tuple[int, int]:
    """Return [start, end) page indices spanning the numbered guidelines."""
    start = end = None
    for i in range(doc.page_count):
        text = doc[i].get_text()
        if start is None and _START_HEADING in text and re.search(
            rf"^\s*\d+\s+{re.escape(_START_HEADING)}", text, re.MULTILINE
        ):
            start = i
        elif start is not None and _END_HEADING in text:
            end = i
            break
    if start is None:
        raise ValueError(f"could not locate '{_START_HEADING}' heading in PDF")
    return start, end if end is not None else doc.page_count


def parse_eba_gl(path: Path | str = DEFAULT_PDF) -> list[Chunk]:
    """Parse the EBA GL PDF into per-paragraph chunks (section 1 skipped)."""
    loader.check_resolved(path)
    doc = pymupdf.open(path)
    start, end = _find_window(doc)

    chunks: list[Chunk] = []
    section: int = 0  # current top-level section number
    title: Optional[str] = None  # current numbered section heading text
    cur_num: Optional[int] = None
    cur_page: int = 0
    cur_lines: list[str] = []
    expected = 1  # next paragraph number expected (guards false matches)

    def flush() -> None:
        nonlocal cur_num, cur_lines
        if cur_num is None:
            return
        if section > _SKIP_SECTION:
            body = _WS.sub(" ", " ".join(cur_lines)).strip()
            if body:
                ref = f"EBA GL 2017/16 para {cur_num}"
                chunks.append(
                    Chunk.create(
                        source=SOURCE,
                        ref=ref,
                        text=body,
                        paragraph=str(cur_num),
                        title=title,
                        page=cur_page,
                        cross_refs=extract_crossrefs(body),
                    )
                )
        cur_num = None
        cur_lines = []

    for i in range(start, end):
        for line in _page_lines(doc[i]):
            inline = _PARA_INLINE.match(line)
            alone = _PARA_ALONE.match(line)
            num = int((inline or alone).group(1)) if (inline or alone) else None
            if num is not None:
                if num == expected:  # genuine next paragraph
                    flush()
                    cur_num = num
                    cur_page = i + 1  # 1-based page number
                    cur_lines = [line]
                    expected = num + 1
                    continue
                if num == cur_num:  # duplicated number line (layout artefact)
                    continue
                # else: a numbered list item inside a paragraph -> body text
            if _HEADING.match(line):
                flush()
                section = int(_HEADING.match(line).group(1))
                title = line
                continue
            if cur_num is not None:
                cur_lines.append(line)
    flush()
    return chunks
