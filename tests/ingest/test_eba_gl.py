"""Acceptance tests for the EBA GL PDF parser (Task 02 Step 3 / Step 7)."""

from __future__ import annotations

import pytest

from regagent.ingest import schema
from regagent.ingest.eba_gl import parse_eba_gl


@pytest.fixture(scope="module")
def chunks():
    return parse_eba_gl()


def test_section_1_boilerplate_skipped(chunks):
    # Compliance/reporting (paras 1-4) must not appear; substance starts at 5.
    nums = sorted(int(c.paragraph) for c in chunks)
    assert min(nums) >= 5


def test_paragraph_numbers_unique_and_contiguous(chunks):
    nums = sorted(int(c.paragraph) for c in chunks)
    assert len(nums) == len(set(nums))
    assert nums == list(range(nums[0], nums[-1] + 1))  # no gaps -> no stall


def test_every_chunk_has_a_page(chunks):
    for c in chunks:
        assert isinstance(c.page, int) and c.page > 0


def test_no_chunk_is_only_header_or_footer(chunks):
    running_header = "GUIDELINES ON PD ESTIMATION"
    for c in chunks:
        assert running_header not in c.text
        assert len(c.text) > 15  # not a bare page number / stray line


def test_required_fields_and_authority(chunks):
    for c in chunks:
        assert c.source == "EBA_GL_2017_16"
        assert c.authority_level == "guideline"
        assert c.ref.startswith("EBA GL 2017/16 para ")
        assert c.text.strip()
        assert c.article is None


def test_section_heading_kept_as_title(chunks):
    c = next(c for c in chunks if c.paragraph == "5")
    assert c.title and "Subject matter" in c.title


def test_split_line_paragraph_assembled(chunks):
    # Para 100 has its number on its own line in the PDF; text must follow.
    c = next(c for c in chunks if c.paragraph == "100")
    assert c.text.startswith("100. Institutions that have obtained permission")


def test_cross_refs_point_to_crr(chunks):
    # Para 6 cites CRR articles; refs normalise to "CRR Art. N".
    c = next(c for c in chunks if c.paragraph == "6")
    assert any(r.startswith("CRR Art. ") for r in c.cross_refs)


def test_deterministic_byte_identical(tmp_path):
    a, b = parse_eba_gl(), parse_eba_gl()
    pa, pb = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    schema.write_jsonl(a, pa)
    schema.write_jsonl(b, pb)
    assert pa.read_bytes() == pb.read_bytes()
