"""Parse the CRR consolidated HTML (EUR-Lex ELI format) into chunks.

Scope: Part Three, Title II, Chapter 3 (Arts. 142-191), the IRB Approach. The
set of articles expected in the text comes from ``crr_article_scope.yaml`` via
:mod:`regagent.ingest.scope`; nothing is hard-coded here.

One chunk per numbered paragraph; articles with no numbered paragraphs yield a
single whole-article chunk. Each chunk's text is prefixed with the article
number and title. Consolidation artefacts (amendment markers ▼M…/►M…/◄ and the
``modref`` elements that carry them) are stripped and whitespace normalised.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

try:  # bs4 warns when lxml parses this XHTML as HTML; harmless for our purpose.
    from bs4 import XMLParsedAsHTMLWarning

    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
except ImportError:  # pragma: no cover
    pass

from . import loader
from .crossrefs import extract_crossrefs
from .schema import Chunk
from .scope import ArticleScope, load_scope

SOURCE = "CRR"
DEFAULT_HTML = loader.REGULATIONS_DIR / "CRR_Consolidated.html"

# Amendment-marker glyphs to scrub from any residual text (Step 7 forbids these).
_MARKER_CHARS = re.compile(r"[▼►◄]\S*")
_WS = re.compile(r"\s+")

_ARTICLE_NUM = re.compile(r"Article\s+(\d+[a-z]?)")
_PARAG_NUM = re.compile(r"^(\d+[a-z]?)\.")


def _clean(text: str) -> str:
    """Drop residual amendment markers and normalise whitespace."""
    text = _MARKER_CHARS.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _article_number(div: Tag) -> Optional[str]:
    node = div.select_one("p.title-article-norm")
    if node is None:
        return None
    m = _ARTICLE_NUM.search(node.get_text(" ", strip=True))
    return m.group(1) if m else None


def _article_title(div: Tag) -> Optional[str]:
    node = div.select_one("div.eli-title p.stitle-article-norm")
    if node is None:
        return None
    title = _clean(node.get_text(" ", strip=True))
    return title or None


def _strip_artefacts(div: Tag) -> None:
    """Remove amendment-marker and editorial elements in place."""
    for node in div.select("p.modref"):
        node.decompose()


def _prefix(number: str, title: Optional[str]) -> str:
    return f"Article {number} — {title}" if title else f"Article {number}"


def _numbered_paragraphs(div: Tag) -> list[tuple[str, str]]:
    """(paragraph_number, cleaned_text) for each direct-child numbered paragraph."""
    out: list[tuple[str, str]] = []
    for node in div.find_all("div", class_="norm", recursive=False):
        span = node.find("span", class_="no-parag")
        if span is None:
            continue
        m = _PARAG_NUM.match(span.get_text(" ", strip=True))
        if m is None:
            continue
        out.append((m.group(1), _clean(node.get_text(" ", strip=True))))
    return out


def _whole_article_body(div: Tag, number: str, title: Optional[str]) -> str:
    """Cleaned text of an article with no numbered paragraphs (title removed)."""
    for node in div.select("p.title-article-norm, div.eli-title"):
        node.decompose()
    return _clean(div.get_text(" ", strip=True))


def _find_article_div(soup: BeautifulSoup, article_id: str) -> Optional[Tag]:
    return soup.find("div", class_="eli-subdivision", id=f"art_{article_id}")


def parse_crr(
    path: Path | str = DEFAULT_HTML,
    scope: Optional[ArticleScope] = None,
) -> list[Chunk]:
    """Parse the CRR IRB chapter into chunks, in article/paragraph order."""
    scope = scope or load_scope()
    html = loader.read_text(path)
    soup = BeautifulSoup(html, "lxml")

    chunks: list[Chunk] = []
    expected = scope.expected_article_ids()

    def _order_key(aid: str) -> tuple:
        digits = "".join(c for c in aid if c.isdigit())
        letter = aid[len(digits):]
        return (int(digits), letter)

    for article_id in sorted(expected, key=_order_key):
        div = _find_article_div(soup, article_id)
        if div is None:
            raise ValueError(
                f"article {article_id} is in scope (crr_article_scope.yaml) but "
                f"absent from {Path(path).name}; the scope file or the source is stale."
            )
        _strip_artefacts(div)
        number = _article_number(div) or article_id
        title = _article_title(div)
        prefix = _prefix(number, title)

        paragraphs = _numbered_paragraphs(div)
        if paragraphs:
            for para_num, body in paragraphs:
                ref = f"CRR Art. {number}({para_num})"
                text = f"{prefix}\n{body}"
                chunks.append(
                    Chunk.create(
                        source=SOURCE,
                        ref=ref,
                        text=text,
                        article=number,
                        paragraph=para_num,
                        title=title,
                        cross_refs=extract_crossrefs(body, exclude=ref),
                    )
                )
        else:
            body = _whole_article_body(div, number, title)
            ref = f"CRR Art. {number}"
            text = f"{prefix}\n{body}"
            chunks.append(
                Chunk.create(
                    source=SOURCE,
                    ref=ref,
                    text=text,
                    article=number,
                    paragraph=None,
                    title=title,
                    cross_refs=extract_crossrefs(body, exclude=ref),
                )
            )
    return chunks
