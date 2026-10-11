"""Tests for the CRR article-scope reader."""

from __future__ import annotations

from regagent.ingest.scope import load_scope


def test_loads_maintained_scope():
    s = load_scope()
    assert s.first == 142 and s.last == 191
    assert s.repealed == frozenset({"155", "165", "167", "186", "187", "188"})
    assert s.inserted == frozenset({"159a"})
    assert s.consolidation_date == "2025-01-01"


def test_expected_set_is_range_minus_repealed_plus_inserted():
    s = load_scope()
    ids = s.expected_article_ids()
    assert "159a" in ids
    for repealed in ("155", "165", "167", "186", "187", "188"):
        assert repealed not in ids
    assert "142" in ids and "191" in ids
    # 50 integers in [142,191], minus 6 repealed, plus 1 inserted = 45.
    assert len(ids) == 45


def test_repealed_and_range_helpers():
    s = load_scope()
    assert s.is_repealed("155") is True
    assert s.is_repealed("160") is False
    assert s.is_in_range("159a") is True
    assert s.is_in_range("155") is True  # repealed but still in-chapter
    assert s.is_in_range("200") is False
