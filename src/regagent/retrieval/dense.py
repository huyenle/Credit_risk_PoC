"""Dense (embedding) retrieval with sentence-transformers + FAISS.

Embeddings use a configurable model (default ``BAAI/bge-small-en-v1.5``) and a
FAISS ``IndexFlatIP`` over L2-normalised vectors, so inner product equals cosine
similarity. Chunk embeddings are cached to disk keyed by model name and corpus
content, so a rebuild on the same corpus skips re-encoding.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np

from ..ingest import loader
from ..ingest.schema import Chunk

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_CACHE_DIR = loader.REPO_ROOT / "data" / "processed" / "embeddings"

# BGE retrieval models expect this instruction prepended to *queries* only;
# passages (the chunks) are embedded without it. Omitting it badly hurts recall.
_BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


def _corpus_key(model_name: str, chunks: list[Chunk]) -> str:
    h = hashlib.sha256(model_name.encode("utf-8"))
    for c in chunks:
        h.update(c.chunk_id.encode("utf-8"))
    return h.hexdigest()[:16]


class DenseIndex:
    """FAISS inner-product index over normalised chunk embeddings."""

    def __init__(
        self,
        chunks: list[Chunk],
        model_name: str = DEFAULT_MODEL,
        cache_dir: Optional[Path] = None,
    ):
        self.chunks = chunks
        self.model_name = model_name
        self._cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self._model = None  # lazy: query encoding only
        embeddings = self._load_or_encode(chunks)
        self._build_index(embeddings)

    # -- model / embeddings ------------------------------------------------

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        if is_query and self.model_name.startswith("BAAI/bge"):
            texts = [_BGE_QUERY_INSTRUCTION + t for t in texts]
        emb = self._get_model().encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(emb, dtype="float32")

    def _load_or_encode(self, chunks: list[Chunk]) -> np.ndarray:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache = self._cache_dir / f"{_corpus_key(self.model_name, chunks)}.npy"
        if cache.exists():
            return np.load(cache)
        emb = self._encode([c.text for c in chunks])
        np.save(cache, emb)
        return emb

    def _build_index(self, embeddings: np.ndarray) -> None:
        import faiss

        self._dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(self._dim)
        self._index.add(embeddings)

    # -- search ------------------------------------------------------------

    def search(self, query: str, k: int = 5) -> list[tuple[int, float]]:
        """Return the top-``k`` ``(chunk_index, cosine_score)`` pairs, best first."""
        q = self._encode([query], is_query=True)
        k = min(k, len(self.chunks))
        scores, idx = self._index.search(q, k)
        return [(int(i), float(s)) for i, s in zip(idx[0], scores[0]) if i >= 0]
