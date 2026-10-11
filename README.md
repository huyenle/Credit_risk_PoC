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
| `src/regagent/vasicek.py` | IRB (Vasicek) risk-weight formula core (Basel CRE31) |
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

### Two stages, two responsibilities

The two scripts are deliberately separate — one authors the data, the other
grades it independently:

| | `generate_portfolio.py` | `compute_ground_truth.py` |
|---|---|---|
| Role | author the exam | write the answer key |
| Reads | `floors.yaml` + seed | `portfolio.csv` + `floors.yaml` |
| Writes | `portfolio.csv` | `ground_truth.yaml` |
| Does | draws per-exposure **PD, LGD, EAD** (+ maturity, sector, collateral …) and plants known breaches | **checks floors** (`value < floor` → breach) and **computes RWA** before/after floors |
| Randomness | yes (seeded) | none — pure deduction |

The floor from `floors.yaml` appears in both, doing opposite jobs: the generator
uses it to *position* each drawn value (baseline above it, planted breaches
below it); the grader uses the same number to *judge* each value and to compute
`rwa_after`. The generator knows where it planted issues by construction; the
grader rediscovers them from scratch. When the two agree (and the tests assert
they do), the ground truth is trustworthy.

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

## Document ingestion & retrieval (Step 2)

Turns the regulatory sources in `data/regulations/` into clean, citable chunks
and retrieves them. No LLM in this step.

### What each module does

| module | responsibility |
|---|---|
| `ingest/loader.py` | read a raw source; fail loudly if it is still a Git-LFS pointer |
| `ingest/scope.py` | read `crr_article_scope.yaml` → the exact set of CRR articles expected |
| `ingest/schema.py` | `Chunk` dataclass + deterministic JSONL (SHA-256 id, sorted keys) |
| `ingest/crossrefs.py` | provision text → normalised refs, e.g. `["CRR Art. 153"]` |
| `ingest/crr.py` | parse `CRR_Consolidated.html` (Arts. 142–191) → chunks |
| `ingest/eba_gl.py` | parse `EBA_GL_2017_16.pdf` (numbered paragraphs) → chunks |
| `ingest/build.py` | run all parsers → `data/processed/chunks.jsonl` (CLI) |
| `retrieval/bm25.py` | lexical BM25 index over chunk text |
| `retrieval/dense.py` | embedding index (bge-small + FAISS), embeddings cached to disk |
| `retrieval/lookup.py` | exact `get_by_ref`; returns a "repealed" sentinel for repealed articles |
| `retrieval/hybrid.py` | `Retriever`: RRF fusion of BM25 + dense, plus lookup — the public API |

`data/regulations/crr_article_scope.yaml` is human-maintained and is the single
source of truth for which CRR articles exist (range − repealed + inserted).

### What depends on what

```
loader ─┐
scope  ─┤                       crossrefs
schema ─┴──► crr.py / eba_gl.py ────┘
                    │
                build.py ──► data/processed/chunks.jsonl
                    │
        ┌───────────┼────────────┐
     bm25.py     dense.py     lookup.py
        └───────────┼────────────┘
              retrieval.Retriever  ◄── scripts/eval_retrieval.py
```

`schema.Chunk` is the single data type passed between every module. `loader` and
`scope` are leaves; `crossrefs` is a pure text→refs helper reused by both parsers.
Public retrieval API: `Retriever.search(query, source=None, k=5)` and
`Retriever.get_by_ref(ref)`.

### Building and evaluating

```bash
# Parse all available sources -> data/processed/chunks.jsonl (deterministic)
python -m regagent.ingest.build

# Score BM25 / dense / hybrid -> docs/results/retrieval_eval.md
python scripts/eval_retrieval.py
```

Install the extra dependencies with `pip install -e ".[dev,ingest,retrieval]"`.
`data/processed/` (chunks, FAISS/embedding cache) is generated and gitignored.

## Running the tests

```bash
pytest -q
```

The suite regenerates the portfolio and ground truth, then checks determinism,
class mix, schema integrity, that every planted issue is real and every decoy is
compliant, that RWA after floors ≥ RWA before, and that no regulatory number is
hard-coded in the generation code.
