"""Step 6 acceptance tests for the generator and portfolio structure."""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import pandas as pd
import pytest

from regagent import risk_weights
from regagent.rules import Rules, applicable_lgd_floor, applicable_pd_floor

import generate_portfolio as gen

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_CSV = REPO_ROOT / "data" / "portfolio.csv"

RETAIL_CLASSES = {"retail_mortgage", "qrre", "other_retail"}

# (exposure_class, collateral_type) pairs that intentionally carry NO LGD floor.
# A pair appearing in the portfolio must either resolve to a floor in
# floors.yaml or be listed here; otherwise the coverage test fails so a missing
# floor is a deliberate decision, never a silent gap. Empty today — every
# combination in the portfolio currently has a registered floor.
LGD_FLOOR_NOT_REQUIRED: set[tuple[str, str]] = set()

# Regulatory literals that must NOT appear in the data-generation code.
FORBIDDEN_LITERALS = ["0.0005", "0.001", "0.05", "0.30", "0.50", "500000000"]
GREP_FILES = [
    REPO_ROOT / "data" / "generate_portfolio.py",
    REPO_ROOT / "scripts" / "compute_ground_truth.py",
]


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(PORTFOLIO_CSV)


@pytest.fixture(scope="module")
def rules():
    return Rules()


def test_generator_is_deterministic():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = gen.build_portfolio(Rules())
        b = gen.build_portfolio(Rules())
    assert a.to_csv(index=False) == b.to_csv(index=False)


def test_row_count_and_class_mix(df):
    assert len(df) == sum(gen.CLASS_COUNTS.values())
    counts = df["exposure_class"].value_counts().to_dict()
    for cls, target in gen.CLASS_COUNTS.items():
        assert abs(counts[cls] - target) <= 0.05 * target


def test_retail_rows_have_no_maturity_or_revenue(df):
    retail = df[df["exposure_class"].isin(RETAIL_CLASSES)]
    assert retail["maturity_years"].isna().all()
    assert retail["annual_revenue_eur"].isna().all()


def test_corporate_rows_have_maturity_and_revenue(df):
    corp = df[df["exposure_class"].isin({"corporate", "corporate_sme"})]
    assert corp["maturity_years"].notna().all()
    assert corp["annual_revenue_eur"].notna().all()


def test_qrre_type_only_on_qrre(df):
    assert df[df["exposure_class"] != "qrre"]["qrre_type"].isna().all()
    assert df[df["exposure_class"] == "qrre"]["qrre_type"].notna().all()


def test_all_rows_are_airb(df):
    assert (df["approach"] == "A-IRB").all()


def test_every_collateral_combo_has_lgd_floor_or_is_listed(df, rules):
    """Each (class, collateral) in the data has a floor or is listed as none."""
    combos = set(zip(df["exposure_class"], df["collateral_type"]))
    for exposure_class, collateral in combos:
        has_floor = rules.lgd_floor(exposure_class, collateral) is not None
        listed_none = (exposure_class, collateral) in LGD_FLOOR_NOT_REQUIRED
        assert has_floor or listed_none, (
            f"({exposure_class}, {collateral}) has no LGD floor in floors.yaml "
            f"and is not listed in LGD_FLOOR_NOT_REQUIRED"
        )


def test_no_bunching_at_floor_buffer_bound(df, rules):
    """Baselines are redrawn, not clipped: no value sits exactly on the buffer."""
    for row in df.to_dict("records"):
        pf = applicable_pd_floor(row, rules)
        if pf is not None:
            assert row["pd"] != pf * gen.PD_BASELINE_FLOOR_MULT
        lf = applicable_lgd_floor(row, rules)
        if lf is not None:
            assert row["lgd"] != lf * gen.LGD_BASELINE_FLOOR_MULT


def test_rwa_after_floors_ge_before_for_performing(df, rules):
    for row in df.to_dict("records"):
        if int(row["default_flag"]) == 1:
            continue
        before = risk_weights.rwa(row, rules=rules)
        floored = dict(row)
        pf = applicable_pd_floor(row, rules)
        if pf is not None:
            floored["pd"] = max(row["pd"], pf)
        lf = applicable_lgd_floor(row, rules)
        if lf is not None:
            floored["lgd"] = max(row["lgd"], lf)
        after = risk_weights.rwa(floored, rules=rules)
        assert after >= before - 1e-6


def test_zero_ead_row_gives_zero_rwa(df, rules):
    zero = df[df["ead"] == 0.0]
    assert len(zero) >= 1
    for row in zero.to_dict("records"):
        assert risk_weights.rwa(row, rules=rules) == 0.0


def test_no_regulatory_literals_in_generation_code():
    for path in GREP_FILES:
        text = path.read_text()
        for literal in FORBIDDEN_LITERALS:
            # Match the number as a standalone token (not part of a longer number).
            pattern = r"(?<![\d.])" + re.escape(literal) + r"(?![\d])"
            match = re.search(pattern, text)
            assert match is None, (
                f"forbidden regulatory literal {literal!r} found in {path.name}"
            )
