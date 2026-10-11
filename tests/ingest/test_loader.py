"""Tests for the Git-LFS pointer guard."""

from __future__ import annotations

import pytest

from regagent.ingest import loader
from regagent.ingest.loader import LFSPointerError


POINTER = (
    b"version https://git-lfs.github.com/spec/v1\n"
    b"oid sha256:9d83e0...\n"
    b"size 13209460\n"
)


def test_lfs_pointer_detected(tmp_path):
    p = tmp_path / "CRR_Consolidated.html"
    p.write_bytes(POINTER)
    with pytest.raises(LFSPointerError, match="git lfs pull"):
        loader.check_resolved(p)
    with pytest.raises(LFSPointerError):
        loader.read_text(p)


def test_leading_whitespace_pointer_detected(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"\n  " + POINTER)
    with pytest.raises(LFSPointerError):
        loader.check_resolved(p)


def test_real_content_passes(tmp_path):
    p = tmp_path / "real.html"
    p.write_text("<html><body>Article 160</body></html>", encoding="utf-8")
    assert loader.check_resolved(p) == p
    assert "Article 160" in loader.read_text(p)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        loader.check_resolved(tmp_path / "nope.pdf")


def test_committed_sources_are_resolved():
    # The real repo files must not be unresolved pointers when tests run.
    for name in ("CRR_Consolidated.html", "EBA_GL_2017_16.pdf"):
        loader.check_resolved(loader.REGULATIONS_DIR / name)
