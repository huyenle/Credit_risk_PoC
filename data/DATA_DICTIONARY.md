# DATA DICTIONARY — Synthetic IRB Portfolio

> **SYNTHETIC DATA — FOR DEMONSTRATION ONLY.** Every exposure in
> `portfolio.csv` is machine-generated. Nothing here represents a real
> counterparty, loan, or institution. The regulatory values in `floors.yaml` are
> working notes marked `verified: true`. Do not use
> this data or its outputs for any real capital, reporting, or credit decision.

## How it is produced

- Generator: `data/generate_portfolio.py` → `data/portfolio.csv`
- Ground truth: `scripts/compute_ground_truth.py` → `data/ground_truth.yaml`
- **Seed: `20260930`** (single NumPy RNG stream, fixed draw order). Two runs
  produce a byte-identical CSV.
- All rates and probabilities are **decimals** (`0.0005` = 0.05%). Monetary
  amounts are in **EUR**.
- Regulatory floors/thresholds are read only from `data/floors.yaml`; they are
  never hard-coded in the generator or the ground-truth script. Baseline
  floor buffers and planted breach ranges are expressed as fractions of those
  registry values.

## Schema (`portfolio.csv`)

| column | type | units | notes |
|---|---|---|---|
| `exposure_id` | str | — | `EXP0001` … `EXP0500` |
| `exposure_class` | str | — | `corporate`, `corporate_sme`, `retail_mortgage`, `qrre`, `other_retail` |
| `approach` | str | — | always `A-IRB` (all exposures use the Advanced IRB approach) |
| `annual_revenue_eur` | float | EUR | corporates only; blank for retail |
| `sector` | str | — | `agri`, `real_estate`, `manufacturing`, `services`, `trade` |
| `pd` | float | decimal | model PD **before** floors |
| `lgd` | float | decimal | model LGD **before** floors |
| `ead` | float | EUR | exposure at default |
| `maturity_years` | float | years | corporates only (1–5); blank for retail |
| `collateral_type` | str | — | `none`, `residential_re`, `commercial_re`, `financial`, `other_physical` |
| `qrre_type` | str | — | `transactor` / `revolver` for QRRE; blank otherwise |
| `default_flag` | int | 0/1 | 1 = defaulted (PD set to 1.0) |

## Class mix (target = actual)

| class | count |
|---|---|
| corporate | 150 |
| corporate_sme | 100 |
| retail_mortgage | 150 |
| qrre | 50 |
| other_retail | 50 |
| **total** | **500** |

## Baseline distributions

- **PD** — log-normal per class, **redrawn** (not clipped) until it lands in
  `(floor·3, 0.3)` so baseline rows never breach a floor and no values bunch on
  the bound. Median PD by class: retail_mortgage 0.006, corporate 0.012,
  corporate_sme 0.018, other_retail 0.03, qrre 0.04.
- **LGD** — beta per collateral/class (concentration 12). Where a floor applies,
  the draw is **redrawn** until it exceeds `floor·1.15` (again, no clipping, no
  bunching); otherwise a single draw capped at 1.0. Means: residential mortgage
  0.20, corporate collateral 0.25–0.45, other retail 0.45, QRRE (unsecured) 0.65.
- **EAD** — log-normal. Median by class: corporate €5m, corporate_sme €1.5m,
  retail_mortgage €200k, other_retail €15k, qrre €8k.
- **maturity_years** — uniform 1–5 for corporates; blank for retail.
- **annual_revenue_eur** — corporate_sme spread log-uniform over the SME
  turnover band (€5m–€50m); large corporates from €50m up to below the
  large-corporate threshold.

## Planted issues

Floor values below come from `floors.yaml`; the generator reads them and never
hard-codes them. Ground truth re-derives every issue independently from the CSV
and the registry (it does not read a planted-id manifest).

| id | issue | how planted | count |
|---|---|---|---|
| P1 | Corporate PD below floor | corporate_sme rows, all in `agri`, PD in `[floor·0.6, floor·0.98]` | 10 |
| P2 | QRRE revolver PD below floor | QRRE revolvers, PD in `[floor·0.6, floor·0.95]` | 8 |
| P3 | Mortgage LGD below floor | residential_re mortgages, LGD in `[floor·0.4, floor·0.9]` | 12 |
| P4 | Scope breach | corporates with revenue `> large-corporate threshold` kept on `A-IRB` | 4 |
| P5 | Unsecured corporate LGD below floor | `corporate` rows, collateral `none`, revenue below the large-corporate threshold, LGD in `[floor·0.6, floor·0.95]`, spread across sectors | 6 |
| D1 | Decoys — exactly at floor | rows with PD or LGD set **equal** to the floor (compliant; must NOT be flagged) | 4 |
| E1 | Edge cases | defaulted rows (PD = 1.0) plus one EAD = 0 row | 3 + 1 |

Planted rows are disjoint (a row carries at most one planted condition).

## Ground truth (`ground_truth.yaml`)

- Breach rule: strict `<` floor is a breach; a value **equal** to the floor is
  compliant.
- Defaulted exposures are excluded from floor checks and RWA totals and listed
  separately (the Vasicek formula is not defined at PD = 1).
- Per issue: `exposure_ids`, `count`, `rwa_before`, `rwa_after`, `rwa_delta`
  (RWA computed over that issue's affected exposures; P4/D1/E1 carry ids only).
- Totals: portfolio RWA before/after floors, plus breakdowns by exposure class
  and by sector.
