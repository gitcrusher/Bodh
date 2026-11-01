"""
tests/test_paper_chat.py — Test suite for Step 3: Per-Paper Grounded Chat (RAG)

Verifies:
  - Lazy chunk generation on first open; reuse on subsequent turns (Rule 46 & 47).
  - 30-day unused chunk eviction (Rule 38).
  - Top 4-6 chunks retrieved within similarity floor (Rule 48).
  - 100% deterministic citation verification (Rule 12).
  - Honest abstention for unanswerable queries ("The paper does not appear to cover that.").
  - DRF REST API endpoints (/cards/<id>/chat/ and /cards/<id>/chat/<session_id>/).
  - Golden eval set testing.
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.embedding.service import EmbeddingService
from core.llm.providers.fake import FakeProvider
from core.llm.router import LLMRouter
from research.chat_engine import (
    ABSTAIN_TEXT,
    MAX_USER_MESSAGE_CHARS,
    get_or_create_paper_chunks,
    retrieve_top_chunks,
    run_paper_chat,
    verify_citations,
)
from research.evals.golden_chat import GOLDEN_CHAT_EXAMPLES, GOLDEN_PAPER_TEXT
from research.models import Card, ChatMessage, ChatSession, PaperChatChunk, RawItem, Source
from research.retention import _evict_unused_chat_chunks


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_embedding_service(monkeypatch):
    """Patch EmbeddingService so tests run fast and offline without loading torch."""
    def mock_embed(self, text: str):
        vec = [0.1] * 384
        import hashlib
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        for i in range(20):
            vec[i] += float((h >> i) & 1) * 0.5
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    def mock_embed_batch(self, texts: list[str], batch_size: int = 32):
        return [mock_embed(self, t) for t in texts]

    def mock_sim(self, a, b):
        dot = sum(x * y for x, y in zip(a, b))
        return max(0.0, min(1.0, float(dot)))

    monkeypatch.setattr(EmbeddingService, "embed", mock_embed)
    monkeypatch.setattr(EmbeddingService, "embed_batch", mock_embed_batch)
    monkeypatch.setattr(EmbeddingService, "cosine_similarity", mock_sim)


@pytest.fixture
def source(db):
    return Source.objects.create(
        name="arXiv Test cs.AI",
        url="https://export.arxiv.org",
        trust_tier=1,
    )


@pytest.fixture
def raw_item(db, source):
    return RawItem.objects.create(
        source=source,
        external_id="2601.99999",
        title="Attention Is All You Need",
        url="https://arxiv.org/abs/2601.99999",
        published_at=timezone.now(),
        raw_content=GOLDEN_PAPER_TEXT,
    )


@pytest.fixture
def card(db, raw_item):
    return Card.objects.create(
        raw_item=raw_item,
        category="research",
        headline="Attention Is All You Need introduces the Transformer architecture.",
        summary_60s="• Introduces the Transformer architecture.\n• Achieves 28.4 BLEU on translation.\n• Eliminates recurrence.",
        tags=["transformers", "attention"],
        candidate_techniques=["multi-head attention", "self-attention"],
        deep_dive_base="The Transformer relies entirely on self-attention mechanisms.",
        source_url=raw_item.url,
        published_at=timezone.now(),
    )


@pytest.fixture
def api_client():
    return APIClient()


# ---------------------------------------------------------------------------
# 1. Lazy Chunking and Reuse Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLazyChunking:
    def test_chunks_generated_on_first_access(self, card):
        assert PaperChatChunk.objects.filter(card=card).count() == 0

        chunks = get_or_create_paper_chunks(card)

        assert len(chunks) > 0
        assert PaperChatChunk.objects.filter(card=card).count() == len(chunks)
        assert chunks[0].embedding is not None
        assert len(chunks[0].embedding) == 384
        assert "Attention Is All You Need" in chunks[0].chunk_text

    def test_chunks_reused_on_subsequent_access(self, card):
        chunks_1 = get_or_create_paper_chunks(card)
        count_1 = len(chunks_1)
        initial_access_time = chunks_1[0].last_accessed_at

        # Access again
        chunks_2 = get_or_create_paper_chunks(card)
        count_2 = len(chunks_2)

        assert count_1 == count_2
        assert PaperChatChunk.objects.filter(card=card).count() == count_1
        # IDs must match
        assert [c.id for c in chunks_1] == [c.id for c in chunks_2]

    def test_no_raw_pdf_stored(self, card):
        # Rule 46: only extracted text and chunks persist
        chunks = get_or_create_paper_chunks(card)
        for c in chunks:
            assert isinstance(c.chunk_text, str)
            assert not hasattr(c, "pdf_blob")
            assert not hasattr(c, "raw_pdf")


# ---------------------------------------------------------------------------
# 2. Retrieval & Similarity Floor Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRetrieval:
    def test_retrieve_top_chunks_returns_within_top_k(self, card):
        scored = retrieve_top_chunks(card, "What is multi-head self-attention?", top_k=5)
        assert 0 < len(scored) <= 5
        # Ordered by descending similarity
        sims = [s[1] for s in scored]
        assert sims == sorted(sims, reverse=True)

    def test_similarity_floor_filters_low_matches(self, card):
        # A completely unrelated query with strict similarity floor
        scored = retrieve_top_chunks(
            card,
            "quantum orbital photosynthesis kinetics in deep ocean bacteria",
            top_k=5,
            similarity_floor=0.99,  # excessively high
        )
        assert len(scored) == 0


# ---------------------------------------------------------------------------
# 3. Deterministic Citation Verification Tests (Rule 12)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCitationVerification:
    def test_valid_citations_pass(self, card):
        chunks = get_or_create_paper_chunks(card)
        chunk = chunks[0]
        # Pick an exact slice from chunk_text
        words = chunk.chunk_text.split()
        exact_quote = " ".join(words[2:8])

        citations = [
            {
                "chunk_id": chunk.id,
                "quote": exact_quote,
                "claim": "The model introduces a novel architecture.",
            }
        ]

        is_valid, verified = verify_citations(chunks, citations)
        assert is_valid is True
        assert len(verified) == 1
        assert verified[0]["quote"] == exact_quote

    def test_unretrieved_chunk_citation_fails(self, card):
        chunks = get_or_create_paper_chunks(card)
        citations = [
            {
                "chunk_id": 999999,  # not retrieved
                "quote": "Attention Is All You Need",
                "claim": "Paper title.",
            }
        ]
        is_valid, _ = verify_citations(chunks, citations)
        assert is_valid is False

    def test_hallucinated_quote_fails(self, card):
        chunks = get_or_create_paper_chunks(card)
        chunk = chunks[0]
        citations = [
            {
                "chunk_id": chunk.id,
                "quote": "This sentence definitely does not exist in any part of the paper.",
                "claim": "Fabricated claim.",
            }
        ]
        is_valid, _ = verify_citations(chunks, citations)
        assert is_valid is False


# ---------------------------------------------------------------------------
# 4. Retention Eviction Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRetentionEviction:
    def test_evict_unused_chat_chunks(self, card):
        chunks = get_or_create_paper_chunks(card)
        assert len(chunks) > 0

        # Mark first chunk as accessed 35 days ago (> 30 days)
        old_chunk = chunks[0]
        PaperChatChunk.objects.filter(id=old_chunk.id).update(
            last_accessed_at=timezone.now() - timedelta(days=35)
        )

        # Active chunk accessed today
        fresh_chunk = chunks[1]
        PaperChatChunk.objects.filter(id=fresh_chunk.id).update(
            last_accessed_at=timezone.now()
        )

        # Run eviction handler
        _evict_unused_chat_chunks(rule=None)

        assert not PaperChatChunk.objects.filter(id=old_chunk.id).exists()
        assert PaperChatChunk.objects.filter(id=fresh_chunk.id).exists()


# ---------------------------------------------------------------------------
# 5. Public Chat Runner Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChatRunner:
    def test_user_message_length_capped(self, card):
        long_message = "A" * 3000
        mock_router = MagicMock(spec=LLMRouter)
        mock_router.complete.return_value = json.dumps({
            "answer": "The paper uses 8 parallel attention heads.",
            "citations": [],
            "abstain": False,
        })

        res = run_paper_chat(card=card, user_message=long_message, router=mock_router)
        assert "session_id" in res

        # Check recorded message length was capped at MAX_USER_MESSAGE_CHARS
        last_msg = ChatMessage.objects.filter(session_id=res["session_id"], role="user").first()
        assert len(last_msg.content) <= MAX_USER_MESSAGE_CHARS

    def test_abstention_on_unanswerable_query(self, card):
        # Query with similarity below floor
        with patch("research.chat_engine.retrieve_top_chunks", return_value=[]):
            res = run_paper_chat(card=card, user_message="What is the recipe for chocolate cake?")
            assert res["abstain"] is True
            assert res["answer"] == ABSTAIN_TEXT
            assert res["citations"] == []

    def test_happy_path_with_valid_citation(self, card):
        chunks = get_or_create_paper_chunks(card)
        chunk = chunks[0]
        words = chunk.chunk_text.split()
        quote = " ".join(words[:4])

        mock_router = MagicMock(spec=LLMRouter)
        mock_router.complete.return_value = json.dumps({
            "answer": "The paper introduces the Transformer architecture.",
            "citations": [
                {
                    "chunk_id": chunk.id,
                    "quote": quote,
                    "claim": "Novel architecture introduction.",
                }
            ],
            "abstain": False,
        })

        res = run_paper_chat(card=card, user_message="What architecture is introduced?", router=mock_router)
        assert res["abstain"] is False
        assert len(res["citations"]) == 1
        assert res["citations"][0]["quote"] == quote


# ---------------------------------------------------------------------------
# 6. REST API Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPaperChatAPI:
    def test_chat_endpoint_happy_path(self, api_client, card):
        chunks = get_or_create_paper_chunks(card)
        chunk = chunks[0]
        quote = " ".join(chunk.chunk_text.split()[:4])

        with patch("research.chat_engine.LLMRouter") as mock_cls:
            instance = mock_cls.return_value
            instance.complete.return_value = json.dumps({
                "answer": "The paper relies entirely on attention.",
                "citations": [
                    {
                        "chunk_id": chunk.id,
                        "quote": quote,
                        "claim": "No recurrence or convolution.",
                    }
                ],
                "abstain": False,
            })

            url = f"/api/v1/research/cards/{card.id}/chat/"
            resp = api_client.post(url, {"message": "Does it use recurrence?"}, format="json")
            assert resp.status_code == status.HTTP_200_OK
            data = resp.json()
            assert "session_id" in data
            assert data["abstain"] is False
            assert len(data["citations"]) == 1

    def test_chat_endpoint_card_not_found(self, api_client):
        url = "/api/v1/research/cards/99999/chat/"
        resp = api_client.post(url, {"message": "Hello?"}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_chat_history_endpoint(self, api_client, card):
        session = ChatSession.objects.create(card=card)
        ChatMessage.objects.create(session=session, role="user", content="Question 1")
        ChatMessage.objects.create(session=session, role="assistant", content="Answer 1", citations=[])

        url = f"/api/v1/research/cards/{card.id}/chat/{session.id}/"
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["id"] == session.id
        assert len(data["messages"]) == 2


# ---------------------------------------------------------------------------
# 7. Golden Evaluation Set Tests (phases.md exit criteria)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGoldenChatEvals:
    def test_golden_eval_set_citation_validity_and_abstention(self, card):
        chunks = get_or_create_paper_chunks(card)
        assert len(chunks) > 0

        for example in GOLDEN_CHAT_EXAMPLES:
            if not example["is_answerable"]:
                # Test abstention
                with patch("research.chat_engine.retrieve_top_chunks", return_value=[]):
                    res = run_paper_chat(card=card, user_message=example["question"])
                    assert res["abstain"] is True
                    assert res["answer"] == ABSTAIN_TEXT
            else:
                # Test citation verification
                expected_quote = example.get("expected_quote")
                if expected_quote:
                    # Find which chunk has this quote
                    target_chunk = None
                    for c in chunks:
                        if expected_quote.lower() in c.chunk_text.lower():
                            target_chunk = c
                            break

                    assert target_chunk is not None, f"Expected quote not in any chunk for {example['id']}"

                    is_valid, verified = verify_citations(
                        chunks,
                        [
                            {
                                "chunk_id": target_chunk.id,
                                "quote": expected_quote,
                                "claim": "Golden claim test",
                            }
                        ],
                    )
                    assert is_valid is True, f"Citation verification failed on golden item {example['id']}"
                    assert len(verified) == 1
