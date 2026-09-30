"""Thin wrapper over the Vasicek core, dispatching by IRB exposure class.

Public interface (per task spec):
    risk_weight(pd, lgd, exposure_class, maturity=None, turnover_eur=None) -> float
    rwa(row) -> float          # RWA = risk weight * EAD

No regulatory floor is applied here: callers pass the PD/LGD they want evaluated
(raw for "before floors", floored for "after floors"). The only registry value
this module reads is the SME turnover band used by the firm-size adjustment,
which it takes from ``floors.yaml`` via :mod:`regagent.rules`.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from . import vasicek
from .rules import Rules

# Structural coefficient of the SME firm-size adjustment (CRR Art. 153(4)); the
# turnover band it interpolates over is read from floors.yaml, not hard-coded.
_SME_MAX_REDUCTION = 0.04

_CORPORATE_CLASSES = {"corporate", "corporate_sme"}
_RETAIL_CORRELATION = {
    "retail_mortgage": vasicek.residential_mortgage_correlation,
    "qrre": vasicek.qrre_correlation,
    "other_retail": vasicek.other_retail_correlation,
}

# Lazily-created shared registry so the required signature stays floor-free while
# the SME adjustment can still read its turnover band from the registry.
_default_rules: Optional[Rules] = None


def _get_rules(rules: Optional[Rules]) -> Rules:
    global _default_rules
    if rules is not None:
        return rules
    if _default_rules is None:
        _default_rules = Rules()
    return _default_rules


def _sme_firm_size_reduction(turnover_eur: float, rules: Rules) -> float:
    """Correlation reduction for an SME, interpolated over the turnover band."""
    lower = rules.threshold("sme_turnover_lower_eur")
    upper = rules.threshold("sme_turnover_upper_eur")
    s = min(max(turnover_eur, lower), upper)
    return _SME_MAX_REDUCTION * (1 - (s - lower) / (upper - lower))


def risk_weight(
    pd: float,
    lgd: float,
    exposure_class: str,
    maturity: Optional[float] = None,
    turnover_eur: Optional[float] = None,
    rules: Optional[Rules] = None,
) -> float:
    """Risk weight for a performing exposure, dispatched by exposure class.

    All rates are decimals. ``maturity`` (years) is required for corporate
    classes and ignored for retail. ``turnover_eur`` is required for
    ``corporate_sme`` (drives the firm-size adjustment). Raises ValueError for
    defaulted PD (pd >= 1) or unknown classes.
    """
    if pd >= 1.0:
        raise ValueError(
            "risk_weight is for performing exposures; handle defaulted (PD=1) "
            "exposures separately."
        )

    if exposure_class in _CORPORATE_CLASSES:
        if maturity is None:
            raise ValueError(f"maturity is required for {exposure_class}")
        correlation = vasicek.corporate_sovereign_correlation(pd)
        if exposure_class == "corporate_sme":
            if turnover_eur is None:
                raise ValueError("turnover_eur is required for corporate_sme")
            correlation -= _sme_firm_size_reduction(turnover_eur, _get_rules(rules))
        maturity_factor = vasicek.maturity_adjustment(maturity, pd)
    elif exposure_class in _RETAIL_CORRELATION:
        correlation = _RETAIL_CORRELATION[exposure_class](pd)
        maturity_factor = 1.0  # retail has no maturity adjustment
    else:
        raise ValueError(f"unknown exposure_class: {exposure_class!r}")

    k = vasicek.capital_requirement_performing(pd, lgd, correlation, maturity_factor)
    return vasicek.risk_weight_from_k(k)


def _opt_float(value: Any) -> Optional[float]:
    """Coerce a possibly-blank/NaN cell to float or None."""
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN -> None


def rwa(row: Mapping[str, Any], rules: Optional[Rules] = None) -> float:
    """Risk-weighted assets for a performing row: risk weight * EAD.

    ``row`` is a mapping with the portfolio columns. Raises ValueError for
    defaulted rows (``default_flag == 1``), which must be handled separately.
    """
    if int(row.get("default_flag", 0) or 0) == 1:
        raise ValueError(
            f"row {row.get('exposure_id')} is defaulted; compute defaulted RWA "
            f"separately (not via the Vasicek formula)."
        )
    rw = risk_weight(
        pd=float(row["pd"]),
        lgd=float(row["lgd"]),
        exposure_class=row["exposure_class"],
        maturity=_opt_float(row.get("maturity_years")),
        turnover_eur=_opt_float(row.get("annual_revenue_eur")),
        rules=rules,
    )
    return rw * float(row["ead"])
