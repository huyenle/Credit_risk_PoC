"""Seeded generator for the synthetic IRB portfolio.

Produces ``data/portfolio.csv``: ~500 exposures with realistic per-class
distributions and deliberately planted issues (see ``DATA_DICTIONARY.md`` and
task spec 01). Fully reproducible: a fixed seed and a single RNG stream in fixed
draw order mean two runs yield a byte-identical CSV.

No regulatory number is hard-coded here. Floors and thresholds are read from
``data/floors.yaml`` via :mod:`regagent.rules`; baseline lower-clips and the
planted breach ranges are expressed as fractions of those values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from regagent.rules import Rules, applicable_lgd_floor, applicable_pd_floor

SEED = 20260930
REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_CSV = REPO_ROOT / "data" / "portfolio.csv"

SECTORS = ["agri", "real_estate", "manufacturing", "services", "trade"]

# Target class mix (sums to 500).
CLASS_COUNTS = {
    "corporate": 150,
    "corporate_sme": 100,
    "retail_mortgage": 150,
    "qrre": 50,
    "other_retail": 50,
}

# PD log-normal parameters per class: (median, sigma). Clipped to (min, 0.3),
# where min is derived from the applicable PD floor (never hard-coded).
PD_PARAMS = {
    "corporate": (0.012, 0.7),
    "corporate_sme": (0.018, 0.7),
    "retail_mortgage": (0.006, 0.7),
    "qrre": (0.04, 0.6),
    "other_retail": (0.03, 0.6),
}
PD_UPPER_CLIP = 0.3
# Keep baseline PD comfortably above the floor so baseline never breaches.
PD_BASELINE_FLOOR_MULT = 3.0

# LGD beta means (concentration k below). Corporate keyed by collateral; retail
# keyed by class (residential mortgages low, unsecured retail high).
LGD_MEAN_BY_COLLATERAL = {
    "none": 0.45,
    "commercial_re": 0.35,
    "financial": 0.25,
    "other_physical": 0.40,
}
LGD_MEAN_RETAIL = {
    "retail_mortgage": 0.20,
    "qrre": 0.65,
    "other_retail": 0.45,
}
LGD_CONCENTRATION = 12.0
# Keep baseline LGD above the floor for classes that have one.
LGD_BASELINE_FLOOR_MULT = 1.15

# EAD log-normal parameters per class: (median EUR, sigma).
EAD_PARAMS = {
    "corporate": (5_000_000, 0.8),
    "corporate_sme": (1_500_000, 0.8),
    "retail_mortgage": (200_000, 0.6),
    "qrre": (8_000, 0.7),
    "other_retail": (15_000, 0.7),
}

CORPORATE_COLLATERAL = ["none", "commercial_re", "financial", "other_physical"]

# Planted-issue sizes.
N_P1 = 10  # corporate_sme PD below floor, all in agri
N_P2 = 8  # qrre revolver PD below floor
N_P3 = 12  # residential mortgage LGD below floor
N_P4 = 4  # large corporate on A-IRB (scope breach)
N_D1_PD = 2  # decoys exactly at PD floor
N_D1_LGD = 2  # decoys exactly at LGD floor
N_E1_DEFAULT = 3  # defaulted rows (PD = 1.0)
N_E1_ZERO_EAD = 1  # EAD = 0 row

# Planted breach ranges, as fractions of the applicable floor (kept < 1 so the
# value is strictly below the floor). Decoys use the floor value exactly.
P1_PD_FRAC = (0.6, 0.98)
P2_PD_FRAC = (0.6, 0.95)
P3_LGD_FRAC = (0.4, 0.9)
P4_REVENUE_FRAC = (1.05, 1.5)  # multiples of the large-corporate threshold


def _beta_ab(mean: float, k: float) -> tuple:
    return mean * k, (1 - mean) * k


def _draw_in_range(
    rng: np.random.Generator,
    draw_fn,
    lower: float,
    upper: float,
    max_tries: int = 10_000,
) -> float:
    """Draw from ``draw_fn`` until the sample lands in ``[lower, upper]``.

    Replaces clipping: rejected draws are re-drawn rather than snapped to the
    bound, so no values bunch at ``lower`` or ``upper``. Deterministic given the
    rng state. Raises if the region is effectively unreachable.
    """
    for _ in range(max_tries):
        x = float(draw_fn())
        if lower <= x <= upper:
            return x
    raise RuntimeError(
        f"could not draw a value in [{lower}, {upper}] after {max_tries} tries"
    )


def _lgd_mean(exposure_class: str, collateral: str) -> float:
    if exposure_class in LGD_MEAN_RETAIL:
        return LGD_MEAN_RETAIL[exposure_class]
    return LGD_MEAN_BY_COLLATERAL[collateral]


def build_portfolio(rules: Rules, seed: int = SEED) -> pd.DataFrame:
    """Build the portfolio DataFrame deterministically from ``seed``."""
    rng = np.random.default_rng(seed)

    rows = []
    for exposure_class, count in CLASS_COUNTS.items():
        for _ in range(count):
            rows.append(_baseline_row(exposure_class, rng, rules))

    df = pd.DataFrame(rows)
    df.insert(0, "exposure_id", [f"EXP{i + 1:04d}" for i in range(len(df))])

    _plant_issues(df, rng, rules)

    # Column order per schema.
    columns = [
        "exposure_id",
        "exposure_class",
        "approach",
        "annual_revenue_eur",
        "sector",
        "pd",
        "lgd",
        "ead",
        "maturity_years",
        "collateral_type",
        "qrre_type",
        "default_flag",
    ]
    return df[columns]


def _baseline_row(exposure_class: str, rng: np.random.Generator, rules: Rules) -> dict:
    is_corporate = exposure_class in ("corporate", "corporate_sme")

    # Collateral / qrre_type by class.
    if exposure_class == "retail_mortgage":
        collateral = "residential_re"
        qrre_type = np.nan
    elif exposure_class == "qrre":
        collateral = "none"
        qrre_type = rng.choice(["transactor", "revolver"])
    elif exposure_class == "other_retail":
        collateral = "none"
        qrre_type = np.nan
    else:
        collateral = rng.choice(CORPORATE_COLLATERAL)
        qrre_type = np.nan

    row = {
        "exposure_class": exposure_class,
        "approach": "A-IRB",
        "sector": rng.choice(SECTORS),
        "collateral_type": collateral,
        "qrre_type": qrre_type,
        "default_flag": 0,
    }

    # PD: log-normal, redrawn to sit above the floor buffer and below the cap.
    median, sigma = PD_PARAMS[exposure_class]
    pd_floor = applicable_pd_floor(row, rules) or 0.0
    row["pd"] = _draw_in_range(
        rng,
        lambda: np.exp(rng.normal(np.log(median), sigma)),
        lower=pd_floor * PD_BASELINE_FLOOR_MULT,
        upper=PD_UPPER_CLIP,
    )

    # LGD: beta, redrawn to sit above the floor buffer (if a floor applies) and
    # at or below 1.0. Mirrors the PD draw above.
    mean = _lgd_mean(exposure_class, collateral)
    a, b = _beta_ab(mean, LGD_CONCENTRATION)
    lgd_floor = applicable_lgd_floor(row, rules) or 0.0
    row["lgd"] = _draw_in_range(
        rng,
        lambda: rng.beta(a, b),
        lower=lgd_floor * LGD_BASELINE_FLOOR_MULT,
        upper=1.0,
    )

    # EAD: log-normal.
    ead_median, ead_sigma = EAD_PARAMS[exposure_class]
    row["ead"] = float(np.exp(rng.normal(np.log(ead_median), ead_sigma)))

    # Corporate-only fields.
    if is_corporate:
        row["maturity_years"] = float(rng.uniform(1.0, 5.0))
        if exposure_class == "corporate_sme":
            lower = rules.threshold("sme_turnover_lower_eur")
            upper = rules.threshold("sme_turnover_upper_eur")
            row["annual_revenue_eur"] = float(
                np.exp(rng.uniform(np.log(lower), np.log(upper)))
            )
        else:
            lower = rules.threshold("sme_turnover_upper_eur")
            upper = rules.threshold("large_corporate_revenue_eur") * 0.9
            row["annual_revenue_eur"] = float(
                np.exp(rng.uniform(np.log(lower), np.log(upper)))
            )
    else:
        row["maturity_years"] = np.nan
        row["annual_revenue_eur"] = np.nan

    return row


def _pick(rng: np.random.Generator, pool: list, n: int, used: set) -> list:
    """Choose ``n`` unused indices from ``pool`` (deterministic given rng state)."""
    available = np.array([i for i in pool if i not in used])
    chosen = rng.choice(available, size=n, replace=False)
    chosen = [int(i) for i in chosen]
    used.update(chosen)
    return chosen


def _plant_issues(df: pd.DataFrame, rng: np.random.Generator, rules: Rules) -> None:
    used: set = set()

    def idx(cls: str) -> list:
        return list(df.index[df["exposure_class"] == cls])

    corp = idx("corporate")
    sme = idx("corporate_sme")
    mort = idx("retail_mortgage")
    revolvers = list(df.index[(df["exposure_class"] == "qrre") & (df["qrre_type"] == "revolver")])

    # P4: large corporate revenue over the threshold, still on A-IRB.
    threshold = rules.threshold("large_corporate_revenue_eur")
    for i in _pick(rng, corp, N_P4, used):
        df.at[i, "annual_revenue_eur"] = float(
            threshold * rng.uniform(*P4_REVENUE_FRAC)
        )

    # P1: 10 corporate_sme in agri with PD below the corporate_sme floor.
    sme_floor = rules.pd_floor("corporate_sme")
    for i in _pick(rng, sme, N_P1, used):
        df.at[i, "sector"] = "agri"
        df.at[i, "pd"] = float(sme_floor * rng.uniform(*P1_PD_FRAC))

    # P2: 8 qrre revolvers with PD below the revolver floor.
    rev_floor = rules.pd_floor("qrre", "revolver")
    for i in _pick(rng, revolvers, N_P2, used):
        df.at[i, "pd"] = float(rev_floor * rng.uniform(*P2_PD_FRAC))

    # P3: 12 residential mortgages with LGD below the mortgage floor.
    mort_floor = rules.lgd_floor("retail_mortgage", "residential_re")
    for i in _pick(rng, mort, N_P3, used):
        df.at[i, "lgd"] = float(mort_floor * rng.uniform(*P3_LGD_FRAC))

    # D1: decoys exactly at the floor (compliant; must NOT be flagged).
    corp_floor = rules.pd_floor("corporate")
    for i in _pick(rng, corp, N_D1_PD, used):
        df.at[i, "pd"] = float(corp_floor)
    for i in _pick(rng, mort, N_D1_LGD, used):
        df.at[i, "lgd"] = float(mort_floor)

    # E1: defaulted rows (PD = 1.0) and one EAD = 0 row.
    default_pool = corp + mort + list(df.index[df["exposure_class"] == "qrre"])
    for i in _pick(rng, default_pool, N_E1_DEFAULT, used):
        df.at[i, "default_flag"] = 1
        df.at[i, "pd"] = 1.0
    for i in _pick(rng, corp + sme, N_E1_ZERO_EAD, used):
        df.at[i, "ead"] = 0.0


def main() -> None:
    rules = Rules()
    df = build_portfolio(rules)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(df)} exposures to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
