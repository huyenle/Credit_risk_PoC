# CLAUDE.md — Regulatory RAG Agent for Credit Risk (PoC)

## What this project is
A portfolio proof-of-concept: a LangGraph agent that takes a risk manager's task, plans
the steps, retrieves provisions from credit risk regulation (CRR3, EBA GL/2017/16,
ECB Guide to Internal Models, SR 26-2), applies them to a synthetic IRB portfolio via
deterministic tools, and returns a cited memo.

Core design principle: **the agent decides what to do; the tools determine the answer.**
The LLM never computes numbers. Every figure comes from tested Python code; every
regulatory claim cites a retrieved passage.

## Build order (do not skip ahead)
1. Synthetic portfolio + ground truth  ← current task: see `docs/tasks/01_synthetic_portfolio.md`
2. Document ingestion + hybrid retrieval (BM25 + embeddings)
3. Tools (`search_regulation`, `get_article`, `query_portfolio`, `compute_rwa`)
4. LangGraph agent (planner → executor → reflector → verifier → reporter)
5. Evaluation harness (golden set, agent vs plain-RAG baseline)
6. Streamlit demo + model card

## Repo layout
```
data/          generator, portfolio.csv, floors.yaml, ground_truth.yaml, DATA_DICTIONARY.md
src/regagent/  package code (risk weights, tools, retrieval, agent)
scripts/       one-off scripts (e.g. compute_ground_truth.py)
tests/         pytest tests, mirroring src/ structure
docs/tasks/    task specs — read the relevant one before starting work
```

## Conventions
- Python 3.11+. Dependencies managed in `pyproject.toml`.
- Type hints on all public functions; short docstrings stating units (decimals, not %).
- Probabilities and rates are decimals: 0.0005 means 0.05%.
- Every new function gets pytest tests. Run `pytest -q` before declaring a step done.
- Fixed random seeds everywhere; outputs must be reproducible byte-for-byte.
- Small, readable modules over clever code.

## Hard rules
- **Never invent or change regulatory values.** Floors, thresholds and article references
  live only in `data/floors.yaml`, which the human maintains. Read from it; never hard-code
  regulatory numbers in Python. If a value you need is missing, stop and ask.
- **Reuse the existing risk-weight module** (see task spec) rather than rewriting the
  IRB formula. If it is missing or its interface is unclear, stop and ask.
- Do not add LLM/LangChain dependencies until step 4 unless the task spec says so.
- Before a multi-file change, show a short plan and wait for approval.
- When you make an assumption, list it at the end of your reply.