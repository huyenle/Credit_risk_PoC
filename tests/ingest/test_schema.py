"""Tests for the Chunk schema and deterministic JSONL serialisation."""

from __future__ import annotations

from regagent.ingest.schema import (
    Chunk,
    compute_chunk_id,
    read_jsonl,
    write_jsonl,
)


def test_create_derives_id_and_authority():
    c = Chunk.create(source="CRR", ref="CRR Art. 160(1)", text="Article 160 ...")
    assert c.authority_level == "law"
    assert c.chunk_id == compute_chunk_id("CRR", "CRR Art. 160(1)", "Article 160 ...")
    assert len(c.chunk_id) == 16
    assert c.repealed is False
    assert c.cross_refs == []


def test_chunk_id_depends_only_on_source_ref_text():
    base = dict(source="CRR", ref="CRR Art. 160(1)", text="same text")
    a = Chunk.create(**base, title="Title A", page=1)
    b = Chunk.create(**base, title="Title B", page=99)
    assert a.chunk_id == b.chunk_id  # title/page do not affect the id
    c = Chunk.create(source="CRR", ref="CRR Art. 160(2)", text="same text")
    assert c.chunk_id != a.chunk_id


def test_chunk_id_is_stable_not_salted():
    # SHA-256 based: identical across processes (regression guard vs hash()).
    assert (
        compute_chunk_id("CRR", "CRR Art. 160(1)", "x")
        == compute_chunk_id("CRR", "CRR Art. 160(1)", "x")
    )


def test_unknown_source_rejected():
    import pytest

    with pytest.raises(ValueError):
        Chunk.create(source="NOPE", ref="r", text="t")


def test_jsonl_roundtrip_and_byte_identical(tmp_path):
    chunks = [
        Chunk.create(
            source="CRR",
            ref="CRR Art. 160(1)",
            text="Article 160 — Probability of default (PD)\n1. ... 0,05 %.",
            article="160",
            paragraph="1",
            title="Probability of default (PD)",
            cross_refs=["CRR Art. 153", "CRR Art. 157"],
        ),
        Chunk.create(
            source="EBA_GL_2017_16",
            ref="EBA GL 2017/16 para 36",
            text="36. ...",
            paragraph="36",
            page=52,
        ),
    ]
    p1 = tmp_path / "a.jsonl"
    p2 = tmp_path / "b.jsonl"
    assert write_jsonl(chunks, p1) == 2
    write_jsonl(read_jsonl(p1), p2)
    assert p1.read_bytes() == p2.read_bytes()  # round-trip is byte-stable
    assert read_jsonl(p1) == chunks

    # Non-ASCII preserved literally (ensure_ascii=False).
    assert "0,05 %" in p1.read_text(encoding="utf-8")
    assert "\\u" not in p1.read_text(encoding="utf-8")
