"""Compute ground truth for the synthetic portfolio, independent of agent code.

Loads ``data/portfolio.csv`` and ``data/floors.yaml``, flags floor breaches with
a strict ``<`` comparison (at-floor is compliant), computes RWA before and after
applying PD/LGD floors via :mod:`regagent.risk_weights`, and writes
``data/ground_truth.yaml``.

This script imports only the risk-weight wrapper and the rule registry — no
future agent code. Defaulted exposures (PD = 1) are excluded from floor checks
and RWA totals and listed separately. No regulatory number is hard-coded; all
floors and thresholds come from the registry.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from regagent import risk_weights
from regagent.rules import Rules, applicable_lgd_floor, applicable_pd_floor

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_CSV = REPO_ROOT / "data" / "portfolio.csv"
OUTPUT_YAML = REPO_ROOT / "data" / "ground_truth.yaml"

SEED = 20260930


def _floored_row(row: dict, rules: Rules) -> dict:
    """Copy of a row with PD and LGD raised to their applicable floors."""
    out = dict(row)
    pd_floor = applicable_pd_floor(row, rules)
    if pd_floor is not None:
        out["pd"] = max(row["pd"], pd_floor)
    lgd_floor = applicable_lgd_floor(row, rules)
    if lgd_floor is not None:
        out["lgd"] = max(row["lgd"], lgd_floor)
    return out


def _rwa_pair(row: dict, rules: Rules) -> tuple:
    """(RWA before floors, RWA after floors) for a performing row."""
    before = risk_weights.rwa(row, rules=rules)
    after = risk_weights.rwa(_floored_row(row, rules), rules=rules)
    return before, after


def _issue_block(rows: list, rules: Rules, extra: dict) -> dict:
    ids = sorted(r["exposure_id"] for r in rows)
    before = sum(_rwa_pair(r, rules)[0] for r in rows)
    after = sum(_rwa_pair(r, rules)[1] for r in rows)
    block = {
        "exposure_ids": ids,
        "count": len(ids),
        "rwa_before": round(before, 2),
        "rwa_after": round(after, 2),
        "rwa_delta": round(after - before, 2),
    }
    block.update(extra)
    return block


def compute(rules: Rules) -> dict:
    df = pd.read_csv(PORTFOLIO_CSV)
    records = df.to_dict("records")

    performing = [r for r in records if int(r["default_flag"]) == 0]
    defaulted = [r for r in records if int(r["default_flag"]) == 1]

    # Per-row breach classification.
    pd_breaches, lgd_breaches = [], []
    for r in performing:
        pf = applicable_pd_floor(r, rules)
        if pf is not None and r["pd"] < pf:
            pd_breaches.append(r)
        lf = applicable_lgd_floor(r, rules)
        if lf is not None and r["lgd"] < lf:
            lgd_breaches.append(r)

    # Categorise breaches into planted issues.
    p1 = [r for r in pd_breaches if r["exposure_class"] in ("corporate", "corporate_sme")]
    p2 = [r for r in pd_breaches if r["exposure_class"] == "qrre" and r.get("qrre_type") == "revolver"]
    p3 = [r for r in lgd_breaches if r["exposure_class"] == "retail_mortgage"]

    # P4: scope breach — large corporate over the threshold still on A-IRB.
    threshold = rules.threshold("large_corporate_revenue_eur")
    p4 = [
        r
        for r in performing
        if r["exposure_class"] == "corporate"
        and float(r["annual_revenue_eur"]) > threshold
        and r["approach"] == "A-IRB"
    ]

    # D1: decoys exactly at a floor (compliant; must not be breaches).
    decoys = []
    for r in performing:
        pf = applicable_pd_floor(r, rules)
        lf = applicable_lgd_floor(r, rules)
        if (pf is not None and r["pd"] == pf) or (lf is not None and r["lgd"] == lf):
            decoys.append(r)

    # Totals by class and sector (performing only), before and after floors.
    by_class: dict = {}
    by_sector: dict = {}
    total_before = total_after = 0.0
    for r in performing:
        before, after = _rwa_pair(r, rules)
        total_before += before
        total_after += after
        for bucket, key in ((by_class, r["exposure_class"]), (by_sector, r["sector"])):
            agg = bucket.setdefault(
                key, {"count": 0, "rwa_before": 0.0, "rwa_after": 0.0}
            )
            agg["count"] += 1
            agg["rwa_before"] += before
            agg["rwa_after"] += after

    def _finalise(bucket: dict) -> dict:
        out = {}
        for key in sorted(bucket):
            agg = bucket[key]
            out[key] = {
                "count": agg["count"],
                "rwa_before": round(agg["rwa_before"], 2),
                "rwa_after": round(agg["rwa_after"], 2),
                "rwa_delta": round(agg["rwa_after"] - agg["rwa_before"], 2),
            }
        return out

    pd_floor_corp = rules.pd_floor("corporate_sme")
    pd_floor_rev = rules.pd_floor("qrre", "revolver")
    lgd_floor_mort = rules.lgd_floor("retail_mortgage", "residential_re")

    return {
        "meta": {
            "seed": SEED,
            "portfolio_csv": PORTFOLIO_CSV.name,
            "floors_yaml": rules.path.name,
            "n_exposures": len(records),
            "n_performing": len(performing),
            "n_defaulted": len(defaulted),
            "breach_rule": "value < floor is a breach; value == floor is compliant",
        },
        "totals": {
            "rwa_before_floors": round(total_before, 2),
            "rwa_after_floors": round(total_after, 2),
            "rwa_delta": round(total_after - total_before, 2),
            "by_exposure_class": _finalise(by_class),
            "by_sector": _finalise(by_sector),
        },
        "issues": {
            "P1": _issue_block(
                p1,
                rules,
                {
                    "description": "Corporate PD below floor (corporate_sme, agri)",
                    "rule": "pd < pd_floor",
                    "floor": pd_floor_corp,
                },
            ),
            "P2": _issue_block(
                p2,
                rules,
                {
                    "description": "QRRE revolver PD below floor",
                    "rule": "pd < pd_floor",
                    "floor": pd_floor_rev,
                },
            ),
            "P3": _issue_block(
                p3,
                rules,
                {
                    "description": "Residential mortgage LGD below floor",
                    "rule": "lgd < lgd_floor",
                    "floor": lgd_floor_mort,
                },
            ),
            "P4": {
                "description": "Large corporate over revenue threshold still on A-IRB",
                "rule": "annual_revenue_eur > threshold and approach == 'A-IRB'",
                "threshold": threshold,
                "exposure_ids": sorted(r["exposure_id"] for r in p4),
                "count": len(p4),
            },
            "D1": {
                "description": "Decoys exactly at a floor (compliant; not breaches)",
                "exposure_ids": sorted(r["exposure_id"] for r in decoys),
                "count": len(decoys),
            },
            "E1": {
                "description": "Edge cases: defaulted rows and a zero-EAD row",
                "defaulted_ids": sorted(r["exposure_id"] for r in defaulted),
                "count_defaulted": len(defaulted),
                "zero_ead_ids": sorted(
                    r["exposure_id"] for r in performing if float(r["ead"]) == 0.0
                ),
            },
        },
        "defaulted": {
            "exposure_ids": sorted(r["exposure_id"] for r in defaulted),
            "count": len(defaulted),
        },
    }


def _to_plain(obj):
    """Recursively convert numpy scalars/containers to plain Python types."""
    import numpy as np

    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def main() -> None:
    rules = Rules()
    result = _to_plain(compute(rules))
    with open(OUTPUT_YAML, "w") as fh:
        yaml.safe_dump(result, fh, sort_keys=False, default_flow_style=False)
    print(f"Wrote ground truth to {OUTPUT_YAML}")


if __name__ == "__main__":
    main()
