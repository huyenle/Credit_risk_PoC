"""Tests for BM25 tokenisation and retrieval."""

from __future__ import annotations

from regagent.retrieval.bm25 import BM25Index, tokenize


def test_tokenizer_keeps_numbers_and_paren_refs():
    toks = tokenize("The PD floor in Article 160(1) is 0,05 %.")
    assert "160(1)" in toks  # parenthesised ref survives as one token
    assert "pd" in toks
    assert "0" in toks and "05" in toks  # "0,05" splits on the comma
    # A bare article number tokenises on its own when not parenthesised.
    assert tokenize("see Article 153 and")[2] == "153"


def test_bm25_finds_relevant_chunk(corpus):
    idx = BM25Index(corpus)
    hits = idx.search("probability of default PD floor", k=5)
    refs = {corpus[i].ref for i, _ in hits}
    assert any(r.startswith("CRR Art. 160") for r in refs)


def test_bm25_is_deterministic(corpus):
    idx = BM25Index(corpus)
    a = idx.search("LGD estimation defaulted exposures", k=5)
    b = idx.search("LGD estimation defaulted exposures", k=5)
    assert [i for i, _ in a] == [i for i, _ in b]
