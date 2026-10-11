"""Tests for exact-reference lookup, including repealed sentinels."""

from __future__ import annotations

from regagent.retrieval.lookup import get_by_ref


def test_article_returns_all_paragraphs_in_order(corpus):
    out = get_by_ref(corpus, "CRR Art. 160")
    assert len(out) >= 2
    assert all(c.article == "160" for c in out)
    paras = [c.paragraph for c in out]
    assert paras == sorted(paras, key=lambda p: (int("".join(ch for ch in p if ch.isdigit())), p))


def test_single_paragraph_lookup(corpus):
    out = get_by_ref(corpus, "CRR Art. 160(1)")
    assert len(out) == 1
    assert out[0].paragraph == "1"
    assert out[0].text.startswith("Article 160 — Probability of default (PD)")


def test_repealed_article_returns_sentinel_not_empty(corpus):
    out = get_by_ref(corpus, "CRR Art. 155")
    assert len(out) == 1
    assert out[0].repealed is True
    assert "repealed" in out[0].text.lower()


def test_eba_paragraph_lookup(corpus):
    out = get_by_ref(corpus, "EBA GL 2017/16 para 36")
    assert len(out) == 1
    assert out[0].source == "EBA_GL_2017_16"
    assert out[0].paragraph == "36"


def test_unknown_ref_returns_empty(corpus):
    assert get_by_ref(corpus, "CRR Art. 9999") == []
