# Task 02 — Document ingestion + hybrid retrieval

## Goal
Turn the regulatory documents into clean, citable chunks and build a retriever that
reliably finds the right provision. No LLM in this step. Output is used by the tools
in Task 03 (`search_regulation`, `get_article`).

## Scope
- **Week 1 (implement now):** CRR (consolidated, IRB chapter Arts. 142–191) and
  EBA GL/2017/16.
- **Week 2 (design for, implement later):** ECB Guide to Internal Models (June 2026)
  and SR 26-2. The chunk schema and parser interface must accommodate them, but do not
  write their parsers yet.

## Inputs (downloaded manually by me — do NOT scrape or download)
```
data/regulations/crr.pdf
data/regulations/crr3.pdf
data/regulations/EBA_GL_2017_16.pdf
data/regulations/EBA_Guide_Internal_Model.pdf
data/regulations/sources.yaml          # file, retrieved_on, url
```
If a file is missing, stop and tell me.

## Deliverables
```
src/regagent/ingest/
  schema.py        Chunk dataclass + JSONL read/write
  crr.py           CRR HTML parser
  eba_gl.py        EBA GL PDF parser
  crossrefs.py     cross-reference extraction
  build.py         CLI: parse all available sources → data/processed/chunks.jsonl
src/regagent/retrieval/
  bm25.py          BM25 index (rank_bm25)
  dense.py         embedding index (sentence-transformers + FAISS)
  hybrid.py        reciprocal rank fusion + source filter
  lookup.py        exact reference lookup (no embeddings)
data/processed/    chunks.jsonl, faiss index, bm25 pickle (gitignored if large)
data/eval/retrieval_queries.yaml   (I write this — see Step 6)
scripts/eval_retrieval.py
tests/ingest/, tests/retrieval/
```

## Step 1 — Chunk schema
```python
@dataclass
class Chunk:
    chunk_id: str          # stable: hash of (source, ref, text)
    source: str            # "CRR" | "EBA_GL_2017_16" | "ECB_GUIDE" | "SR_26_2"
    authority_level: str   # "law" | "guideline" | "supervisory_expectation" | "foreign_guidance"
    ref: str               # human-citable, e.g. "CRR Art. 160(1)", "EBA GL 2017/16 para 36"
    article: str | None    # e.g. "160" (CRR only)
    paragraph: str | None  # e.g. "1"
    title: str | None      # article or section title
    page: int | None       # PDFs only
    text: str
    cross_refs: list[str]  # normalised refs found in text, e.g. ["CRR Art. 153"]
```
Authority level is set per source in one mapping in `schema.py`, not per chunk.

## Step 2 — CRR parser (`crr.py`)
- Parse only Part Three, Title II, Chapter 3 (Arts. 142–191).
- One chunk per numbered paragraph; if an article has no numbered paragraphs, one chunk
  per article. Keep point lists (a), (b)… inside their paragraph chunk.
- Prefix each chunk's text with the article number and title for retrieval context,
  e.g. `"Article 160 — Probability of default (PD)\n1. ..."`.
- Strip consolidation artefacts: amendment markers (▼M…, ►M…, ◄), footnote markers,
  and editorial notes. Normalise whitespace.
- Handle inserted articles (e.g. `142a`) as valid article numbers.

## Step 3 — EBA GL parser (`eba_gl.py`)
- Use PyMuPDF. Remove repeated page headers/footers (detect lines recurring on most pages).
- Chunk by numbered paragraph of the guidelines (the guidelines number their paragraphs);
  keep the enclosing section heading as `title`. Record `page`.
- Skip the cover, table of contents, and the "Compliance and reporting obligations"
  boilerplate section.

## Step 4 — Cross-references (`crossrefs.py`)
- Regex-extract references like `Article 153`, `Article 160(1)`, `Articles 161 to 163`,
  `point (a) of Article 164(4)`; normalise to `CRR Art. N` / `CRR Art. N(p)`.
- Ranges expand to individual articles.
- Unit-test against at least 10 hand-written strings.

## Step 5 — Retrieval
- **BM25** over `text` with simple tokenisation (lowercase, keep numbers and
  parentheses so "160(1)" survives).
- **Dense:** sentence-transformers model `BAAI/bge-small-en-v1.5` (configurable),
  FAISS `IndexFlatIP` on normalised embeddings. Cache embeddings to disk.
- **Hybrid:** reciprocal rank fusion, `score = Σ 1/(k + rank)`, k = 60, over the
  top 50 of each retriever. Optional `source` filter applied before fusion.
- **Lookup:** `get_by_ref("CRR Art. 160")` returns all paragraph chunks of that
  article in order; `get_by_ref("CRR Art. 160(1)")` returns that paragraph. No
  embeddings involved.
- Public API: `search(query, source=None, k=5) -> list[Chunk]` and
  `get_by_ref(ref) -> list[Chunk]`.

## Step 6 — Retrieval evaluation
I will write `data/eval/retrieval_queries.yaml` with ~15 items:
```yaml
- query: "minimum PD for corporate exposures"
  expected_refs: ["CRR Art. 160(1)"]
```
`scripts/eval_retrieval.py` reports hit@1, hit@5 and MRR for BM25-only, dense-only and
hybrid, as a markdown table printed and saved to `docs/results/retrieval_eval.md`.
Create the script and an example file with 2 placeholder items; do NOT write the real
queries yourself.

## Step 7 — Tests (acceptance criteria)
- Every article number 142–191 (plus any lettered insertions present) yields ≥1 chunk.
- No chunk text contains amendment markers (▼, ►, ◄).
- Every chunk has non-empty `ref`, `source`, `authority_level`, `text`.
- `chunk_id`s are unique and stable across two builds (byte-identical `chunks.jsonl`).
- `get_by_ref("CRR Art. 160(1)")` returns exactly one chunk whose text starts with the
  Article 160 prefix.
- Cross-reference unit tests pass; a known CRR paragraph that cites Art. 153 has
  `"CRR Art. 153"` in `cross_refs`.
- EBA GL: no chunk consists only of header/footer text; every chunk has a `page`.
- `search("PD floor corporate", source="CRR")` returns only CRR chunks.
- Hybrid hit@5 ≥ max(BM25, dense) hit@5 on the placeholder eval file (sanity check).

## Dependencies to add
`beautifulsoup4`, `lxml`, `pymupdf`, `rank_bm25`, `sentence-transformers`, `faiss-cpu`.
(No LangChain yet — that arrives in Task 03/04.)

## Working instructions
1. Read `CLAUDE.md` and this file. Inspect the raw files' structure first (e.g. print
   the HTML structure around Article 160 and the first pages of the EBA PDF) and show me
   what you find before writing parsers.
2. Propose a plan; wait for my approval.
3. Implement Step 1 → 7, running `pytest -q` after each step. Existing Task 01 tests must
   keep passing.
4. Finish with: files created, test results, retrieval eval table, assumptions made.