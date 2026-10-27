"""
Embedding service — one pinned model, never routed through provider fallback.

Rule (rules.md rule 23, design doc 14.1):
  "One pinned embedding model. Never route embeddings through provider fallback.
   Every vector stores embedding_model_version. Changing the model is a deliberate
   re-embed migration, not a failover."

Model: sentence-transformers/all-MiniLM-L6-v2
  - 384 dimensions
  - Runs locally — no API cost, no rate limits, no key required
  - ~80MB download on first use, then cached by sentence-transformers
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from django.conf import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# This must match the EMBEDDING_MODEL setting. If the setting changes,
# all vectors must be re-embedded — a deliberate migration, never automatic.
PINNED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
PINNED_DIM = 384


class EmbeddingService:
    """
    Wraps a pinned sentence-transformers model.

    The model is loaded lazily on first call so startup is fast.
    Thread-safe: sentence-transformers encode() releases the GIL.
    """

    def __init__(self) -> None:
        self._model: SentenceTransformer | None = None
        self._model_name = getattr(settings, "EMBEDDING_MODEL", PINNED_MODEL_NAME)
        self._dim = getattr(settings, "EMBEDDING_DIM", PINNED_DIM)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        """The version string stored on every vector row (embedding_model_version)."""
        return self._model_name.replace("/", "__")

    def _load(self) -> SentenceTransformer:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # lazy

            logger.info("Loading embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
            actual_dim = self._model.get_sentence_embedding_dimension()
            if actual_dim != self._dim:
                raise RuntimeError(
                    f"Embedding model {self._model_name!r} has {actual_dim} dims, "
                    f"but settings.EMBEDDING_DIM={self._dim}. "
                    "Update EMBEDDING_DIM or switch to the pinned model."
                )
        return self._model

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.
        Returns a list of floats (length = PINNED_DIM).
        """
        model = self._load()
        vector: np.ndarray = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Embed multiple texts in one pass.
        Returns a list of float lists.
        """
        if not texts:
            return []
        model = self._load()
        vectors: np.ndarray = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.tolist()

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """
        Cosine similarity between two already-normalized vectors.
        Since embed() normalizes, this equals the dot product.
        """
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        return float(np.dot(va, vb))


# Module-level singleton — the one pinned instance
embedding_service = EmbeddingService()
