"""Step 7 sanity check: hybrid hit@5 >= max(BM25, dense) on the eval file."""

from __future__ import annotations

from pathlib import Path

import yaml

from eval_retrieval import DEFAULT_QUERIES, evaluate


def test_hybrid_hit_at_5_not_worse_than_best_single():
    queries = yaml.safe_load(Path(DEFAULT_QUERIES).read_text(encoding="utf-8"))
    results = evaluate(queries)
    best_single = max(results["BM25"]["hit@5"], results["Dense"]["hit@5"])
    assert results["Hybrid"]["hit@5"] >= best_single
