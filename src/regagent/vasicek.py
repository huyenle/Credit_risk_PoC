"""IRB (Vasicek) risk-weight formula core.

Copied from the project's existing ``CRE31_RWA.py`` (corporate/sovereign case)
and extended with the retail asset-correlation formulas. The Vasicek math is
NOT modified: the corporate correlation and maturity-adjustment functions are
byte-for-byte the originals.

Structural constants of the Basel/CRE31 formula (asset-correlation coefficients,
the 99.9% confidence level, and the ``RW = K * 12.5`` multiplier) live here as
code — they are not floors or thresholds. Regulatory floors and thresholds live
only in ``data/floors.yaml`` and are applied by the callers, never here. In
particular this module does NOT floor PD: pass the PD you want evaluated.

All rates and probabilities are decimals (0.0005 == 0.05%).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

# Basel multiplier to convert a capital requirement (K) into a risk weight.
# RW = K * 12.5 (i.e. 1 / 8% minimum capital ratio). The finalised Basel III
# framework removed the old 1.06 scaling factor, so it is not applied.
RW_MULTIPLIER = 12.5

# Confidence level for the conditional (worst-case) default rate.
CONFIDENCE_LEVEL = 0.999


def corporate_sovereign_correlation(pd: float) -> float:
    """Asset correlation (R) for corporate/sovereign exposures, per CRE31."""
    lower_weight = (1 - np.exp(-50 * pd)) / (1 - np.exp(-50))
    return 0.12 * lower_weight + 0.24 * (1 - lower_weight)


def residential_mortgage_correlation(pd: float) -> float:
    """Asset correlation for residential mortgage exposures: fixed R = 0.15."""
    return 0.15


def qrre_correlation(pd: float) -> float:
    """Asset correlation for qualifying revolving retail exposures: fixed R = 0.04."""
    return 0.04


def other_retail_correlation(pd: float) -> float:
    """Asset correlation for other retail exposures, per CRE31 (PD-dependent)."""
    lower_weight = (1 - np.exp(-35 * pd)) / (1 - np.exp(-35))
    return 0.03 * lower_weight + 0.16 * (1 - lower_weight)


def maturity_adjustment(maturity: float, pd: float) -> float:
    """Maturity adjustment applied to corporate/sovereign exposures."""
    b = (0.11852 - 0.05478 * np.log(pd)) ** 2
    return 1 / (1 - 1.5 * b) + (maturity - 2.5) * b / (1 - 1.5 * b)


def conditional_pd(pd: float, correlation: float) -> float:
    """Conditional (worst-case) default rate at the confidence level."""
    return float(
        norm.cdf(
            norm.ppf(pd) * np.sqrt(1 / (1 - correlation))
            + norm.ppf(CONFIDENCE_LEVEL) * np.sqrt(correlation / (1 - correlation))
        )
    )


def capital_requirement_performing(
    pd: float, lgd: float, correlation: float, maturity_factor: float = 1.0
) -> float:
    """Capital requirement rate (K) for a performing exposure.

    ``correlation`` is the asset correlation for the exposure's class and
    ``maturity_factor`` is the maturity adjustment (1.0 for retail, which has no
    maturity adjustment). PD is used as given; no floor is applied here.
    """
    return lgd * (conditional_pd(pd, correlation) - pd) * maturity_factor


def risk_weight_from_k(k: float) -> float:
    """Convert a capital requirement rate (K) into a risk weight: RW = K * 12.5."""
    return k * RW_MULTIPLIER
