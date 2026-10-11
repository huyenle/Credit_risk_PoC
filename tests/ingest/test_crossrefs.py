"""Unit tests for cross-reference extraction (>=10 hand-written strings)."""

from __future__ import annotations

from regagent.ingest.crossrefs import extract_crossrefs


def test_single_article():
    assert extract_crossrefs("in accordance with Article 153") == ["CRR Art. 153"]


def test_article_with_paragraph():
    assert extract_crossrefs("see Article 160(1) of") == ["CRR Art. 160(1)"]


def test_range_expands():
    assert extract_crossrefs("as set out in Articles 161 to 163") == [
        "CRR Art. 161",
        "CRR Art. 162",
        "CRR Art. 163",
    ]


def test_point_of_article():
    assert extract_crossrefs("point (a) of Article 164(4)") == ["CRR Art. 164(4)"]


def test_and_list():
    assert extract_crossrefs("Articles 161 and 162") == [
        "CRR Art. 161",
        "CRR Art. 162",
    ]


def test_inserted_letter_article():
    assert extract_crossrefs("pursuant to Article 159a") == ["CRR Art. 159a"]


def test_multiple_mixed_sorted_and_deduped():
    text = (
        "Articles 153 and 157, and Article 158(1), (5) and (10); "
        "see also Article 153 again and Articles 161 to 163."
    )
    assert extract_crossrefs(text) == [
        "CRR Art. 153",
        "CRR Art. 157",
        "CRR Art. 158(1)",
        "CRR Art. 161",
        "CRR Art. 162",
        "CRR Art. 163",
    ]


def test_paragraph_and_bare_same_article_both_kept():
    # Art. 147 appears bare and with a paragraph -> two distinct refs.
    refs = extract_crossrefs("Article 147(2), point (b), and Article 147 generally")
    assert "CRR Art. 147(2)" in refs
    assert "CRR Art. 147" in refs


def test_exclude_self_reference():
    text = "Article 160 — this is Article 160 and also Article 153"
    assert extract_crossrefs(text, exclude="CRR Art. 160") == ["CRR Art. 153"]


def test_no_references():
    assert extract_crossrefs("This paragraph cites nothing at all.") == []


def test_numeric_sort_not_lexical():
    # 9 must sort before 100 numerically.
    assert extract_crossrefs("Article 100 and Article 9") == [
        "CRR Art. 9",
        "CRR Art. 100",
    ]


def test_cross_chapter_reference_allowed():
    assert extract_crossrefs("as defined in Article 4(1)") == ["CRR Art. 4(1)"]
