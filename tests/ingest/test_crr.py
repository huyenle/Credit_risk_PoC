"""Acceptance tests for the CRR HTML parser (Task 02 Step 2 / Step 7)."""

from __future__ import annotations

import pytest

from regagent.ingest import schema
from regagent.ingest.crr import parse_crr
from regagent.ingest.scope import load_scope


@pytest.fixture(scope="module")
def chunks():
    return parse_crr()


@pytest.fixture(scope="module")
def scope():
    return load_scope()


def test_parsed_articles_exactly_match_scope(chunks, scope):
    # Exact set equality: range - repealed + inserted (no more, no less).
    parsed = {c.article for c in chunks}
    assert parsed == scope.expected_article_ids()


def test_every_in_scope_article_yields_at_least_one_chunk(chunks, scope):
    by_article: dict[str, int] = {}
    for c in chunks:
        by_article[c.article] = by_article.get(c.article, 0) + 1
    for article in scope.expected_article_ids():
        assert by_article.get(article, 0) >= 1


def test_no_amendment_markers_anywhere(chunks):
    for c in chunks:
        assert not any(ch in c.text for ch in "▼►◄")


def test_required_fields_non_empty(chunks):
    for c in chunks:
        assert c.ref and c.source == "CRR"
        assert c.authority_level == "law"
        assert c.text.strip()
        assert c.article


def test_article_160_1_is_single_and_prefixed(chunks):
    matches = [c for c in chunks if c.ref == "CRR Art. 160(1)"]
    assert len(matches) == 1
    assert matches[0].text.startswith("Article 160 — Probability of default (PD)")
    assert matches[0].paragraph == "1"


def test_known_cross_reference_captured(chunks):
    # Art. 160(1) cites Art. 153 -> normalised ref present.
    c = next(c for c in chunks if c.ref == "CRR Art. 160(1)")
    assert "CRR Art. 153" in c.cross_refs


def test_inserted_article_present(chunks):
    assert any(c.article == "159a" for c in chunks)


def test_whole_article_fallback_for_unparagraphed(chunks):
    # Art. 156 has no numbered paragraphs -> one whole-article chunk.
    matches = [c for c in chunks if c.article == "156"]
    assert len(matches) == 1
    assert matches[0].ref == "CRR Art. 156"
    assert matches[0].paragraph is None


def test_chunk_ids_unique(chunks):
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_build_is_deterministic_byte_identical(tmp_path):
    a = parse_crr()
    b = parse_crr()
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    schema.write_jsonl(a, pa)
    schema.write_jsonl(b, pb)
    assert pa.read_bytes() == pb.read_bytes()
