"""CLI: parse all available regulatory sources into ``data/processed/chunks.jsonl``.

Only sources with an implemented parser and a resolved (non-LFS-pointer) file
are built. The ECB Guide and SR 26-2 are designed for but not yet parsed
(Task 02 Week 2); when their parsers land, register them in ``PARSERS`` and they
flow through unchanged. Output is deterministic (see :mod:`schema`).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from . import crr, eba_gl, loader
from .schema import Chunk, write_jsonl

REPO_ROOT = loader.REPO_ROOT
DEFAULT_OUTPUT = REPO_ROOT / "data" / "processed" / "chunks.jsonl"

# source name -> (raw file, parser). Order fixes chunk order in the output.
PARSERS: dict[str, tuple[Path, Callable[[], list[Chunk]]]] = {
    "CRR": (crr.DEFAULT_HTML, crr.parse_crr),
    "EBA_GL_2017_16": (eba_gl.DEFAULT_PDF, eba_gl.parse_eba_gl),
}


def build_chunks() -> list[Chunk]:
    """Parse every available source and return the combined chunk list."""
    chunks: list[Chunk] = []
    for name, (path, parse) in PARSERS.items():
        if not Path(path).exists():
            print(f"skip {name}: {path} not found")
            continue
        loader.check_resolved(path)  # fail loudly on an unresolved LFS pointer
        parsed = parse()
        print(f"{name}: {len(parsed)} chunks")
        chunks.extend(parsed)
    return chunks


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build regulatory chunks.jsonl")
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args(argv)

    chunks = build_chunks()
    n = write_jsonl(chunks, args.output)
    print(f"wrote {n} chunks to {args.output}")


if __name__ == "__main__":
    main()
