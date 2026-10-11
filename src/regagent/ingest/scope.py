"""CRR IRB-chapter article scope, read from ``crr_article_scope.yaml``.

The YAML is the single source of truth for which articles exist in the
consolidated text: the full range minus repealed articles plus lettered
insertions. The parser uses it to know what to expect, the Step 7 test asserts
exact set equality against it, and ``get_by_ref`` uses it to return an explicit
"repealed" result rather than an empty list. No article numbers are hard-coded
in Python.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCOPE_PATH = REPO_ROOT / "data" / "regulations" / "crr_article_scope.yaml"


@dataclass(frozen=True)
class ArticleScope:
    """In-range article ids expected in the consolidated CRR text."""

    first: int
    last: int
    repealed: frozenset[str]
    inserted: frozenset[str]
    consolidation_date: str

    def expected_article_ids(self) -> set[str]:
        """The exact set of article ids a build should yield.

        ``range(first..last)`` as strings, minus ``repealed``, plus ``inserted``.
        """
        base = {str(n) for n in range(self.first, self.last + 1)}
        return (base - set(self.repealed)) | set(self.inserted)

    def is_repealed(self, article: str) -> bool:
        return article in self.repealed

    def is_in_range(self, article: str) -> bool:
        """True if ``article`` falls within the chapter (incl. repealed/inserted)."""
        if article in self.inserted or article in self.repealed:
            return True
        digits = "".join(ch for ch in article if ch.isdigit())
        return bool(digits) and self.first <= int(digits) <= self.last


def load_scope(path: Optional[Path | str] = None) -> ArticleScope:
    """Load the article scope from YAML (defaults to the maintained file)."""
    p = Path(path) if path is not None else DEFAULT_SCOPE_PATH
    with open(p, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    rng = data["range"]
    return ArticleScope(
        first=int(rng["first"]),
        last=int(rng["last"]),
        repealed=frozenset(str(a) for a in data.get("repealed", [])),
        inserted=frozenset(str(a) for a in data.get("inserted", [])),
        consolidation_date=str(data.get("consolidation_date", "")),
    )
