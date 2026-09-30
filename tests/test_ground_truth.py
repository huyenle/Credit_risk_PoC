"""Step 6 acceptance tests for the ground-truth output."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

from regagent.rules import Rules, applicable_lgd_floor, applicable_pd_floor

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_CSV = REPO_ROOT / "data" / "portfolio.csv"
GROUND_TRUTH_YAML = REPO_ROOT / "data" / "ground_truth.yaml"


@pytest.fixture(scope="module")
def gt():
    return yaml.safe_load(GROUND_TRUTH_YAML.read_text())


@pytest.fixture(scope="module")
def rows():
    df = pd.read_csv(PORTFOLIO_CSV)
    return {r["exposure_id"]: r for r in df.to_dict("records")}


@pytest.fixture(scope="module")
def rules():
    return Rules()


def test_pd_breach_issues_are_real(gt, rows, rules):
    for issue in ("P1", "P2"):
        ids = gt["issues"][issue]["exposure_ids"]
        assert len(ids) == gt["issues"][issue]["count"]
        assert ids, f"{issue} has no ids"
        for eid in ids:
            row = rows[eid]
            floor = applicable_pd_floor(row, rules)
            assert floor is not None
            assert row["pd"] < floor


def test_p3_lgd_breaches_are_real(gt, rows, rules):
    ids = gt["issues"]["P3"]["exposure_ids"]
    assert ids
    for eid in ids:
        row = rows[eid]
        floor = applicable_lgd_floor(row, rules)
        assert floor is not None
        assert row["lgd"] < floor


def test_p4_scope_breaches_are_real(gt, rows, rules):
    threshold = rules.threshold("large_corporate_revenue_eur")
    ids = gt["issues"]["P4"]["exposure_ids"]
    assert ids
    for eid in ids:
        row = rows[eid]
        assert row["exposure_class"] == "corporate"
        assert row["approach"] == "A-IRB"
        assert float(row["annual_revenue_eur"]) > threshold


def test_decoys_are_not_flagged_as_breaches(gt):
    decoys = set(gt["issues"]["D1"]["exposure_ids"])
    assert decoys
    breach_ids = set()
    for issue in ("P1", "P2", "P3"):
        breach_ids.update(gt["issues"][issue]["exposure_ids"])
    assert decoys.isdisjoint(breach_ids)


def test_decoys_sit_exactly_at_a_floor(gt, rows, rules):
    for eid in gt["issues"]["D1"]["exposure_ids"]:
        row = rows[eid]
        pf = applicable_pd_floor(row, rules)
        lf = applicable_lgd_floor(row, rules)
        at_pd = pf is not None and row["pd"] == pf
        at_lgd = lf is not None and row["lgd"] == lf
        assert at_pd or at_lgd


def test_no_breaches_outside_planted_issues(gt, rows, rules):
    """Every actual floor breach must be accounted for by P1/P2/P3."""
    planted = set()
    for issue in ("P1", "P2", "P3"):
        planted.update(gt["issues"][issue]["exposure_ids"])

    actual = set()
    for row in rows.values():
        if int(row["default_flag"]) == 1:
            continue
        pf = applicable_pd_floor(row, rules)
        if pf is not None and row["pd"] < pf:
            actual.add(row["exposure_id"])
        lf = applicable_lgd_floor(row, rules)
        if lf is not None and row["lgd"] < lf:
            actual.add(row["exposure_id"])

    assert actual == planted


def test_defaulted_excluded_and_listed(gt, rows):
    defaulted = gt["defaulted"]["exposure_ids"]
    assert gt["defaulted"]["count"] == len(defaulted)
    assert defaulted == gt["issues"]["E1"]["defaulted_ids"]
    for eid in defaulted:
        assert int(rows[eid]["default_flag"]) == 1
    # Defaulted rows must not appear in any floor-breach issue.
    breach_ids = set()
    for issue in ("P1", "P2", "P3"):
        breach_ids.update(gt["issues"][issue]["exposure_ids"])
    assert set(defaulted).isdisjoint(breach_ids)


def test_per_issue_rwa_after_ge_before(gt):
    for issue in ("P1", "P2", "P3"):
        block = gt["issues"][issue]
        assert block["rwa_after"] >= block["rwa_before"]
        assert block["rwa_delta"] == pytest.approx(
            block["rwa_after"] - block["rwa_before"], abs=0.01
        )


def test_totals_present(gt):
    totals = gt["totals"]
    assert totals["rwa_after_floors"] >= totals["rwa_before_floors"]
    assert set(totals["by_exposure_class"]) == set(
        ["corporate", "corporate_sme", "retail_mortgage", "qrre", "other_retail"]
    )
    assert len(totals["by_sector"]) == 5
