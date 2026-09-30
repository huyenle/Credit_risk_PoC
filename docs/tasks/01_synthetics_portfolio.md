# Task 01 — Synthetic IRB portfolio + ground truth

## Goal
Build a reproducible synthetic IRB portfolio (~500 exposures) with realistic structure
and **deliberately planted issues** whose correct answers are known in advance. It
serves as (a) the data the agent queries and (b) the ground truth the evaluation
checks the agent against.

## Deliverables
```
data/generate_portfolio.py     seeded generator → data/portfolio.csv
data/floors.yaml               rule registry (human-maintained; see below)
data/DATA_DICTIONARY.md        columns, units, distributions, planted issues, "SYNTHETIC" disclaimer
scripts/compute_ground_truth.py  independent of any agent code → data/ground_truth.yaml
src/regagent/risk_weights.py   thin wrapper around the existing risk-weight module
tests/test_portfolio.py
tests/test_ground_truth.py
```

## Step 0 — Existing risk-weight module
I already have a unit-tested Python module implementing the IRB (Vasicek) risk-weight
formula at: `CRE31_RWA.py`.
- Copy or import it; do NOT rewrite the formula.
- Wrap it in `src/regagent/risk_weights.py` exposing:
  `risk_weight(pd, lgd, exposure_class, maturity=None, turnover_eur=None) -> float`
  and `rwa(row) -> float` (RWA = risk weight × EAD).
- If the existing module lacks a class we need (e.g. QRRE, SME adjustment), stop and
  tell me what's missing instead of improvising.

## Step 1 — floors.yaml (rule registry)
Create `data/floors.yaml` with the structure below. The values are from my own notes and
are marked `verified: false` until I have checked them against the consolidated CRR text.
Do not change values; read them in code from this file only.

```yaml
pd_floors:
  - {exposure_class: corporate,       value: 0.0005, ref: "CRR Art. 160(1)", verified: false}
  - {exposure_class: corporate_sme,   value: 0.0005, ref: "CRR Art. 160(1)", verified: false}
  - {exposure_class: retail_mortgage, value: 0.0005, ref: "CRR Art. 163(1)", verified: false}
  - {exposure_class: other_retail,    value: 0.0005, ref: "CRR Art. 163(1)", verified: false}
  - {exposure_class: qrre, qrre_type: transactor, value: 0.0005, ref: "CRR Art. 163(1)", verified: false}
  - {exposure_class: qrre, qrre_type: revolver,   value: 0.0010, ref: "CRR Art. 163(1)", verified: false}
lgd_floors:   # retail: Art. 164(4); corporate A-IRB: Art. 161(5) — FILL/VERIFY
  - {exposure_class: retail_mortgage, collateral_type: residential_re, value: 0.05, ref: "CRR Art. 164(4)", verified: false}
  - {exposure_class: qrre,            collateral_type: none,           value: 0.50, ref: "CRR Art. 164(4)", verified: false}
  - {exposure_class: other_retail,    collateral_type: none,           value: 0.30, ref: "CRR Art. 164(4)", verified: false}
  # corporate LGD floors: add after verification
thresholds:
  large_corporate_revenue_eur: {value: 500000000, ref: "CRR3 — VERIFY article", verified: false}
  sme_turnover_upper_eur:      {value: 50000000,  ref: "CRR Art. 153(4)", verified: false}
  sme_turnover_lower_eur:      {value: 5000000,   ref: "CRR Art. 153(4)", verified: false}
```
Code must print a warning when it uses any entry with `verified: false`.

## Step 2 — Portfolio schema
| column | type | notes |
|---|---|---|
| exposure_id | str | e.g. `EXP0001` |
| exposure_class | str | corporate, corporate_sme, retail_mortgage, qrre, other_retail |
| approach | str | `A-IRB` or `F-IRB` |
| annual_revenue_eur | float | corporates only; blank for retail |
| sector | str | agri, real_estate, manufacturing, services, trade |
| pd | float | model PD before floors, decimal |
| lgd | float | model LGD before floors, decimal |
| ead | float | EUR |
| maturity_years | float | corporates only (1–5); blank for retail |
| collateral_type | str | none, residential_re, commercial_re, financial, other_physical |
| qrre_type | str | transactor / revolver for QRRE; blank otherwise |
| default_flag | int | 1 = defaulted (PD = 1.0) |

Target mix (approx.): 150 corporate, 100 corporate_sme, 150 retail_mortgage,
50 qrre, 50 other_retail. Seed: `20260930`.

## Step 3 — Realistic baseline distributions
- PD: log-normal per class, clipped to (0, 0.3); levels plausible per class
  (mortgages lowest, QRRE/other retail highest).
- LGD: beta per collateral type (residential_re low, none high).
- EAD: log-normal; corporates in the millions, retail in the tens/hundreds of thousands.
- maturity_years: uniform 1–5 for corporates.
- annual_revenue_eur: SME corporates spread across 5–50m; large corporates above.
- Baseline rows must NOT accidentally breach floors — breaches come only from Step 4.

## Step 4 — Planted issues (record every affected exposure_id)
| id | issue | how to plant |
|---|---|---|
| P1 | Corporate PD below floor | ~10% of corporate_sme, concentrated in ONE sector (agri), PD in [0.0003, 0.00049] |
| P2 | QRRE revolver PD below floor | ~8 revolvers with PD in [0.0006, 0.00095] |
| P3 | Mortgage LGD below floor | ~12 residential_re mortgages with LGD in [0.02, 0.045] |
| P4 | Scope breach | ~4 corporates with revenue > large-corporate threshold still on `A-IRB` |
| D1 | Decoys — exactly at floor | a few rows with PD or LGD exactly equal to the floor (compliant; must NOT be flagged) |
| E1 | Edge cases | 3 defaulted rows (PD = 1.0), 1 row with EAD = 0 |

Floor values must be read from `floors.yaml`, not hard-coded.

## Step 5 — Ground truth (independent script)
`scripts/compute_ground_truth.py` must NOT import any future agent code. It:
1. Loads `portfolio.csv` and `floors.yaml`.
2. Flags breaches per rule (strict `<` floor; at-floor is compliant).
3. Computes RWA before and after applying PD and LGD floors, via `risk_weights.py`.
   Defaulted exposures: exclude from floor checks and from RWA totals; list them separately.
4. Writes `data/ground_truth.yaml` containing, per planted issue: exposure_ids, count,
   RWA before, RWA after, delta; plus totals by exposure_class and by sector; plus the
   list of scope breaches (P4) and decoy ids (D1).

## Step 6 — Tests (acceptance criteria)
- Generator is deterministic: two runs → identical CSV.
- Row count and class mix within ±5% of targets.
- No maturity or revenue on retail rows; qrre_type only on QRRE rows.
- Every planted id in ground_truth is actually present and actually breaches its rule.
- No decoy is flagged as a breach.
- Excluding planted issues, zero floor breaches in the portfolio.
- RWA after floors ≥ RWA before for every non-defaulted row.
- EAD = 0 row yields RWA = 0 without error.
- No regulatory number appears as a literal in `generate_portfolio.py` or
  `compute_ground_truth.py` (grep test for 0.0005, 0.001, 0.05, 0.30, 0.50, 500000000).

## Step 7 — DATA_DICTIONARY.md
Columns, units, distributions, the planted-issue table, the seed, and a clear statement
that the data is synthetic and for demonstration only.

## Working instructions
1. Read `CLAUDE.md` and this file. Propose a short plan; wait for my approval.
2. Implement in order Step 0 → 7. Run `pytest -q` after each step.
3. Finish with: files created, test results, and a list of assumptions made.