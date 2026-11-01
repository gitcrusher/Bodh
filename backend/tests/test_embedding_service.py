"""Tests for EmbeddingService (pinned model, dimension check, cosine similarity)."""

from unittest.mock import MagicMock
import numpy as np
import pytest
from core.embedding.service import PINNED_DIM, PINNED_MODEL_NAME, EmbeddingService


def test_embedding_service_properties():
    svc = EmbeddingService()
    assert svc.model_name == PINNED_MODEL_NAME
    assert "MiniLM" in svc.model_version


def test_embedding_cosine_similarity():
    svc = EmbeddingService()
    # Normalized vectors
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    c = [0.0, 1.0, 0.0]
    assert pytest.approx(svc.cosine_similarity(a, b), 0.001) == 1.0
    assert pytest.approx(svc.cosine_similarity(a, c), 0.001) == 0.0


def test_embedding_service_mock_embed():
    svc = EmbeddingService()
    mock_model = MagicMock()
    mock_model.get_sentence_embedding_dimension.return_value = PINNED_DIM
    mock_model.encode.return_value = np.zeros(PINNED_DIM, dtype=float)
    svc._model = mock_model

    vec = svc.embed("Transformer architecture")
    assert len(vec) == PINNED_DIM
    assert mock_model.encode.called
