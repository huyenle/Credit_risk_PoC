"""Evaluate BM25-only, dense-only and hybrid retrieval on a query set.

Reports hit@1, hit@5 and MRR per retriever as a markdown table, printed and
saved to ``docs/results/retrieval_eval.md``. A query counts as a hit at rank r
if any of its ``expected_refs`` appears among the top-r retrieved refs.

Usage:
    python scripts/eval_retrieval.py [--queries data/eval/retrieval_queries.yaml]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from regagent.ingest.build import build_chunks
from regagent.retrieval.bm25 import BM25Index
from regagent.retrieval.dense import DenseIndex
from regagent.retrieval.hybrid import Retriever

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUERIES = REPO_ROOT / "data" / "eval" / "retrieval_queries.yaml"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "results" / "retrieval_eval.md"
TOP_K = 5


def _first_hit_rank(refs: list[str], expected: set[str]) -> int | None:
    """1-based rank of the first retrieved ref in ``expected``, else None."""
    for rank, ref in enumerate(refs, start=1):
        if ref in expected:
            return rank
    return None


def _metrics(ranked_refs: list[list[str]], expected: list[set[str]]) -> dict:
    hit1 = hit5 = mrr = 0.0
    n = len(expected)
    for refs, exp in zip(ranked_refs, expected):
        rank = _first_hit_rank(refs[:TOP_K], exp)
        if rank is not None:
            hit5 += 1
            if rank == 1:
                hit1 += 1
            mrr += 1.0 / rank
    return {"hit@1": hit1 / n, "hit@5": hit5 / n, "mrr": mrr / n}


def evaluate(queries: list[dict]) -> dict[str, dict]:
    chunks = build_chunks()
    bm25 = BM25Index(chunks)
    dense = DenseIndex(chunks)
    hybrid = Retriever(chunks=chunks)

    expected = [set(q["expected_refs"]) for q in queries]

    bm25_refs, dense_refs, hybrid_refs = [], [], []
    for q in queries:
        query = q["query"]
        bm25_refs.append([chunks[i].ref for i, _ in bm25.search(query, k=TOP_K)])
        dense_refs.append([chunks[i].ref for i, _ in dense.search(query, k=TOP_K)])
        hybrid_refs.append([c.ref for c in hybrid.search(query, k=TOP_K)])

    return {
        "BM25": _metrics(bm25_refs, expected),
        "Dense": _metrics(dense_refs, expected),
        "Hybrid": _metrics(hybrid_refs, expected),
    }


def to_markdown(results: dict[str, dict], n_queries: int) -> str:
    lines = [
        f"# Retrieval evaluation ({n_queries} queries)",
        "",
        "| Retriever | hit@1 | hit@5 | MRR |",
        "|---|---|---|---|",
    ]
    for name, m in results.items():
        lines.append(
            f"| {name} | {m['hit@1']:.3f} | {m['hit@5']:.3f} | {m['mrr']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Evaluate retrieval variants")
    ap.add_argument("--queries", type=Path, default=DEFAULT_QUERIES)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args(argv)

    with open(args.queries, "r", encoding="utf-8") as fh:
        queries = yaml.safe_load(fh)

    results = evaluate(queries)
    md = to_markdown(results, len(queries))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
