"""
tests/test_paper_linker.py

Unit tests for Dynamic Research Linking Engine (Rule 56 & 57).
Tests ingest-time dynamic link creation, relation classification,
and dynamic paper links API endpoint.
"""

from datetime import datetime, timezone
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from research.models import Card, CardRelation, RawItem, Source
from research.paper_linker import get_dynamic_paper_links, link_newly_ingested_card


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def source(db):
    return Source.objects.create(
        name="arXiv CS.AI",
        url="https://arxiv.org/list/cs.AI/recent",
        fetch_method="scraper",
        trust_tier=1,
    )


@pytest.fixture
def sample_cards(db, source):
    # Card 1: Attention & Transformers
    raw_1 = RawItem.objects.create(
        source=source,
        external_id="1706.03762",
        title="Attention Is All You Need",
        url="https://arxiv.org/abs/1706.03762",
        published_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        status="processed",
    )
    card_1 = Card.objects.create(
        raw_item=raw_1,
        headline="Attention Is All You Need",
        summary_60s="• Proposes Transformer architecture.\n• Uses multi-head self-attention.",
        tags=["transformers", "attention", "nlp"],
        candidate_techniques=["self-attention", "multi-head attention"],
        source_url=raw_1.url,
        published_at=raw_1.published_at,
    )

    # Card 2: Shared Technique (multi-head attention)
    raw_2 = RawItem.objects.create(
        source=source,
        external_id="2407.08608",
        title="FlashAttention-3: Fast Attention with Asynchrony",
        url="https://arxiv.org/abs/2407.08608",
        published_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        status="processed",
    )
    card_2 = Card.objects.create(
        raw_item=raw_2,
        headline="FlashAttention-3: Fast and Accurate Attention",
        summary_60s="• Accelerates multi-head attention on Hopper GPUs.\n• Uses warp specialization.",
        tags=["hardware", "efficiency", "gpu"],
        candidate_techniques=["multi-head attention", "warp-specialization"],
        source_url=raw_2.url,
        published_at=raw_2.published_at,
    )

    # Card 3: Benchmark comparison (GSM8K)
    raw_3 = RawItem.objects.create(
        source=source,
        external_id="2310.12345",
        title="Solving Math Word Problems on GSM8K",
        url="https://arxiv.org/abs/2310.12345",
        published_at=datetime(2026, 10, 3, tzinfo=timezone.utc),
        status="processed",
    )
    card_3 = Card.objects.create(
        raw_item=raw_3,
        headline="Solving Math Problems on GSM8K",
        summary_60s="• Evaluates reasoning on the GSM8K benchmark.",
        tags=["reasoning", "math"],
        candidate_techniques=["chain-of-thought", "gsm8k"],
        source_url=raw_3.url,
        published_at=raw_3.published_at,
    )

    return card_1, card_2, card_3


@pytest.mark.django_db
def test_link_newly_ingested_card_shared_technique(sample_cards):
    card_1, card_2, _ = sample_cards

    # Link card_2 against existing cards (card_1 exists)
    created = link_newly_ingested_card(card_2)

    assert len(created) >= 1
    rel = CardRelation.objects.filter(source_card=card_2, target_card=card_1).first()
    assert rel is not None
    assert rel.relation_type in ["foundational_lineage", "shared_technique"]
    assert "Attention" in rel.relation_label
    assert rel.similarity_score >= 0.85

    # Check reciprocal link exists for card_1 -> card_2
    reciprocal = CardRelation.objects.filter(source_card=card_1, target_card=card_2).first()
    assert reciprocal is not None
    assert reciprocal.relation_type in ["foundational_lineage", "shared_technique"]


@pytest.mark.django_db
def test_link_newly_ingested_card_benchmark_comparison(sample_cards, source):
    _, _, card_3 = sample_cards

    # Ingest a new paper also evaluating GSM8K
    raw_4 = RawItem.objects.create(
        source=source,
        external_id="2410.55555",
        title="GSM8K Step-by-Step Reasoner",
        url="https://arxiv.org/abs/2410.55555",
        published_at=datetime(2026, 10, 4, tzinfo=timezone.utc),
        status="processed",
    )
    card_4 = Card.objects.create(
        raw_item=raw_4,
        headline="GSM8K Step-by-Step Reasoner",
        summary_60s="• Proposes a verified solver on GSM8K benchmark.",
        tags=["reasoning", "evaluation"],
        candidate_techniques=["step-by-step reasoning"],
        source_url=raw_4.url,
        published_at=raw_4.published_at,
    )

    created = link_newly_ingested_card(card_4)
    assert len(created) >= 1
    rel = CardRelation.objects.filter(source_card=card_4, target_card=card_3).first()
    assert rel is not None
    assert rel.relation_type == "benchmark_comparison"
    assert "GSM8K" in rel.relation_label


@pytest.mark.django_db
def test_get_dynamic_paper_links_payload(sample_cards):
    card_1, card_2, _ = sample_cards
    link_newly_ingested_card(card_2)

    links = get_dynamic_paper_links(card_1)
    assert len(links) >= 1
    link_item = links[0]

    assert link_item["target_card_id"] == card_2.id
    assert link_item["target_headline"] == card_2.headline
    assert link_item["relation_type"] in ["foundational_lineage", "shared_technique", "topic_cluster"]
    assert "target_source_url" in link_item
    assert "similarity_score" in link_item


@pytest.mark.django_db
def test_unrelated_ai_papers_are_not_linked(sample_cards, source):
    """
    CRITICAL USER REQUIREMENT:
    Even though both are AI/ML papers, unrelated topics (e.g. GPU hardware tiling
    vs. math reasoning on GSM8K) must NOT be linked together as related papers.
    """
    _, card_flash_attention, card_gsm8k = sample_cards

    # Attempt to link card_flash_attention with card_gsm8k
    CardRelation.objects.all().delete()
    created = link_newly_ingested_card(card_flash_attention)

    # FlashAttention should link to Attention Is All You Need, but NEVER to GSM8K
    linked_target_ids = [r.target_card_id for r in created]
    assert card_gsm8k.id not in linked_target_ids


@pytest.mark.django_db
def test_dynamic_paper_links_api_endpoint(api_client, sample_cards):
    card_1, _, _ = sample_cards

    url = f"/api/v1/research/cards/{card_1.id}/links/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["card_id"] == card_1.id
    assert "topic" in data
    assert "links_count" in data
    assert "links" in data
    assert isinstance(data["links"], list)

