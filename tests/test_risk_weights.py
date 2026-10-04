"""Step 0 tests: the risk-weight wrapper behaves correctly across exposure classes."""

from __future__ import annotations

import warnings

import pytest

from regagent import risk_weights, vasicek
from regagent.rules import Rules


def test_rwa_multiplies_ead_last():
    row = {
        "exposure_id": "EXP0001",
        "exposure_class": "corporate",
        "pd": 0.02,
        "lgd": 0.45,
        "maturity_years": 2.5,
        "ead": 1_000_000.0,
        "default_flag": 0,
    }
    rw = risk_weights.risk_weight(0.02, 0.45, "corporate", maturity=2.5)
    assert risk_weights.rwa(row) == pytest.approx(rw * 1_000_000.0)


def test_ead_zero_gives_zero_rwa():
    row = {
        "exposure_id": "EXP0002",
        "exposure_class": "retail_mortgage",
        "pd": 0.01,
        "lgd": 0.2,
        "ead": 0.0,
        "default_flag": 0,
    }
    assert risk_weights.rwa(row) == 0.0


def test_defaulted_row_raises():
    row = {
        "exposure_id": "EXP0003",
        "exposure_class": "corporate",
        "pd": 1.0,
        "lgd": 0.45,
        "maturity_years": 2.5,
        "ead": 1_000_000.0,
        "default_flag": 1,
    }
    with pytest.raises(ValueError):
        risk_weights.rwa(row)


def test_retail_classes_have_no_maturity_adjustment():
    # For retail, changing maturity must not change the risk weight.
    for cls in ("retail_mortgage", "qrre", "other_retail"):
        rw1 = risk_weights.risk_weight(0.03, 0.4, cls, maturity=1.0)
        rw2 = risk_weights.risk_weight(0.03, 0.4, cls, maturity=5.0)
        assert rw1 == rw2


def test_sme_adjustment_reduces_risk_weight():
    # A small SME (low turnover) gets a larger correlation reduction, hence a
    # lower risk weight than a large one, all else equal.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        small = risk_weights.risk_weight(
            0.02, 0.45, "corporate_sme", maturity=2.5, turnover_eur=5_000_000
        )
        large = risk_weights.risk_weight(
            0.02, 0.45, "corporate_sme", maturity=2.5, turnover_eur=50_000_000
        )
        corp = risk_weights.risk_weight(0.02, 0.45, "corporate", maturity=2.5)
    assert small < large <= corp


def test_correlation_bounds():
    assert vasicek.residential_mortgage_correlation(0.05) == 0.15
    assert vasicek.qrre_correlation(0.05) == 0.04


def test_unverified_value_warns(tmp_path):
    # The warning mechanism must fire for any entry still marked
    # `verified: false`, independent of the production floors.yaml (which may be
    # fully verified). Use a throwaway registry so the test does not depend on
    # the human-maintained flags.
    floors = tmp_path / "floors.yaml"
    floors.write_text(
        "pd_floors:\n"
        "  - {exposure_class: corporate, value: 0.0005, ref: test, verified: false}\n"
    )
    rules = Rules(path=floors)
    with pytest.warns(UserWarning):
        rules.pd_floor("corporate")


def test_unknown_class_raises():
    with pytest.raises(ValueError):
        risk_weights.risk_weight(0.02, 0.45, "sovereign", maturity=2.5)
