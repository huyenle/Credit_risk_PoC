# Regulatory RAG Agent for Credit Risk — PoC

A portfolio proof-of-concept: a LangGraph agent that takes a risk manager's task,
retrieves provisions from credit-risk regulation (CRR3, EBA GL, ECB Guide to
Internal Models, SR 26-2), applies them to a synthetic IRB portfolio via
deterministic tools, and returns a cited memo.

**Core design principle:** the agent decides *what* to do; the tools determine
the *answer*. The LLM never computes numbers — every figure comes from tested
Python, every regulatory claim cites a retrieved passage.

> ⚠️ **Synthetic data, for demonstration only.** The portfolio is machine-
> generated and the regulatory values in `data/floors.yaml` are unverified
> working notes (`verified: false`). Do not use any of this for real capital,
> reporting, or credit decisions.

## What's implemented so far

Step 1 of the build — the **synthetic IRB portfolio and ground truth**:

| path | purpose |
|---|---|
| `src/regagent/vasicek.py` | IRB (Vasicek) risk-weight formula core (from `CRE31_RWA.py`) |
| `src/regagent/risk_weights.py` | wrapper: `risk_weight(...)` / `rwa(row)`, dispatched by exposure class |
| `src/regagent/rules.py` | loads `floors.yaml`; per-row floor/threshold lookups |
| `data/floors.yaml` | rule registry (human-maintained; the only source of regulatory numbers) |
| `data/generate_portfolio.py` | seeded generator → `data/portfolio.csv` |
| `scripts/compute_ground_truth.py` | independent checker → `data/ground_truth.yaml` |
| `data/DATA_DICTIONARY.md` | schema, distributions, planted issues, disclaimer |
| `tests/` | pytest acceptance tests |

## Requirements

- Python 3.11+ (developed and tested against the toolchain in `pyproject.toml`)
- Dependencies: `numpy`, `scipy`, `pandas`, `pyyaml` (plus `pytest` for tests)

```bash
python -m pip install -e ".[dev]"
```

## Generating the portfolio

The generator is fully deterministic (seed `20260930`): two runs produce a
byte-identical CSV.

```bash
# 1. Generate the synthetic portfolio -> data/portfolio.csv
python data/generate_portfolio.py

# 2. Compute the ground truth -> data/ground_truth.yaml
python scripts/compute_ground_truth.py
```

Both scripts read regulatory floors and thresholds **only** from
`data/floors.yaml`. Entries still marked `verified: false` trigger a warning each
time they are used — this is expected until the values are checked against the
consolidated CRR text.

If you run the scripts directly (rather than after `pip install -e`), make the
package importable first:

```bash
PYTHONPATH=src python data/generate_portfolio.py
PYTHONPATH=src python scripts/compute_ground_truth.py
```

## What the data contains

~500 exposures across five IRB classes (corporate, corporate SME, retail
mortgage, QRRE, other retail) with realistic per-class distributions and
**deliberately planted issues** whose correct answers are known in advance
(PD/LGD floor breaches, a scope breach, at-floor decoys, and edge cases). See
[`data/DATA_DICTIONARY.md`](data/DATA_DICTIONARY.md) for the full schema and the
planted-issue table.

`data/ground_truth.yaml` is produced independently of any agent code and lists,
per planted issue, the affected `exposure_id`s and the RWA impact before/after
floors, plus RWA totals by exposure class and by sector.

## Running the tests

```bash
pytest -q
```

The suite regenerates the portfolio and ground truth, then checks determinism,
class mix, schema integrity, that every planted issue is real and every decoy is
compliant, that RWA after floors ≥ RWA before, and that no regulatory number is
hard-coded in the generation code.
