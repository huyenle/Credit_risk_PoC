"""Loader and lookup helpers for the regulatory rule registry (``floors.yaml``).

This is the ONLY place regulatory floors and thresholds enter the code. The
generator, ground-truth script and risk-weight wrapper all read floors from a
:class:`Rules` instance so the per-row lookup is written exactly once.

Any entry still marked ``verified: false`` triggers a warning the first time it
is used (once per distinct rule, to avoid noise).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import yaml

# data/floors.yaml, resolved relative to the repo root (two levels up from here
# is src/regagent; the repo root is three levels up).
DEFAULT_FLOORS_PATH = Path(__file__).resolve().parents[2] / "data" / "floors.yaml"


class Rules:
    """In-memory view of ``floors.yaml`` with per-row floor/threshold lookups."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else DEFAULT_FLOORS_PATH
        with open(self.path, "r") as fh:
            self._data = yaml.safe_load(fh)
        self._warned: set[str] = set()

    # -- internal ---------------------------------------------------------

    def _use(self, entry: dict, warn_key: str) -> float:
        """Return an entry's value, warning once if it is unverified."""
        if not entry.get("verified", False) and warn_key not in self._warned:
            self._warned.add(warn_key)
            warnings.warn(
                f"Using unverified regulatory value '{warn_key}' "
                f"(ref: {entry.get('ref', 'n/a')}, value: {entry['value']}) "
                f"from {self.path.name}",
                stacklevel=2,
            )
        return float(entry["value"])

    # -- floors -----------------------------------------------------------

    def pd_floor(
        self, exposure_class: str, qrre_type: Optional[str] = None
    ) -> Optional[float]:
        """PD floor for an exposure, or None if the registry has none for it."""
        for entry in self._data.get("pd_floors", []):
            if entry["exposure_class"] != exposure_class:
                continue
            if "qrre_type" in entry and entry["qrre_type"] != qrre_type:
                continue
            key = f"pd_floors:{exposure_class}"
            if "qrre_type" in entry:
                key += f":{entry['qrre_type']}"
            return self._use(entry, key)
        return None

    def lgd_floor(
        self, exposure_class: str, collateral_type: Optional[str] = None
    ) -> Optional[float]:
        """LGD floor for an exposure/collateral pair, or None if unregistered."""
        for entry in self._data.get("lgd_floors", []):
            if entry["exposure_class"] != exposure_class:
                continue
            if entry.get("collateral_type") != collateral_type:
                continue
            key = f"lgd_floors:{exposure_class}:{collateral_type}"
            return self._use(entry, key)
        return None

    # -- thresholds -------------------------------------------------------

    def threshold(self, name: str) -> float:
        """Named monetary threshold from the registry."""
        entry = self._data["thresholds"][name]
        return self._use(entry, f"thresholds:{name}")


# Convenience row-based wrappers -----------------------------------------------


def applicable_pd_floor(row: dict, rules: Rules) -> Optional[float]:
    """PD floor applicable to a portfolio row (handles QRRE transactor/revolver)."""
    qrre_type = row.get("qrre_type") or None
    return rules.pd_floor(row["exposure_class"], qrre_type)


def applicable_lgd_floor(row: dict, rules: Rules) -> Optional[float]:
    """LGD floor applicable to a portfolio row, or None if none is registered."""
    collateral = row.get("collateral_type") or None
    return rules.lgd_floor(row["exposure_class"], collateral)
