"""
tests/test_technique_grounding.py

Step 7 — Trending-Technique Grounding Tests (The Reverse Pipeline, Design §9, Rule 52).

Verifies:
1. Rule 52 exact wording for no_literature_found:
   "no published research found for this specific technique yet." (never "unverified" or "debunked").
2. Rule 52 direct_match requires work title or abstract to contain technique name or alias.
3. Related_only verdict connects adjacent literature without claiming direct validation.
4. Technique-cluster fallback for cards without direct social trend signals.
5. REST API endpoints:
   - GET /api/v1/research/techniques/trending/
   - GET /api/v1/research/techniques/{slug}/
   - GET /api/v1/research/cards/{card_id}/grounding/
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from research.models import (
    Card,
    TrendingTechnique,
    TechniqueLiteratureLink,
    RawItem,
    Source,
)
from research.technique_grounding_service import (
    TechniqueGroundingService,
    RULE_52_NO_LITERATURE_WORDING,
    RULE_52_RELATED_WORDING,
)


@pytest.mark.django_db
class TestTechniqueGroundingRule52:
    """Verifies strict adherence to Rule 52 and literature classification."""

    def test_rule_52_no_literature_found_exact_wording(self):
        """Rule 52: Technique grounding wording is 'no published research found for this specific technique yet.' Never 'unverified' or 'debunked.'"""
        status, explanation, matches = TechniqueGroundingService.evaluate_grounding_rule52(
            technique_name="Novel Local Fine-tuning Trick",
            aliases=["LocalTrick-v1"],
            retrieved_works=[],
        )

        assert status == "no_literature_found"
        assert RULE_52_NO_LITERATURE_WORDING in explanation
        assert "unverified" not in explanation.lower()
        assert "debunked" not in explanation.lower()
        assert len(matches) == 0

    def test_rule_52_direct_match_requires_title_or_abstract_match(self):
        """Rule 52: direct_match requires the returned work's title or abstract to contain the technique name or an alias."""
        retrieved_works = [
            {
                "work_id": "corpus_1",
                "source": "semantic_scholar",
                "title": "FlashAttention-3: Fast and Accurate Attention with Asynchrony",
                "snippet": "We introduce FlashAttention-3 for Hopper architectures.",
            }
        ]

        status, explanation, matches = TechniqueGroundingService.evaluate_grounding_rule52(
            technique_name="FlashAttention-3",
            aliases=["FA3"],
            retrieved_works=retrieved_works,
        )

        assert status == "direct_match"
        assert len(matches) == 1
        assert matches[0]["match_type"] == "direct"
        assert "direct literature validation" in explanation.lower()

    def test_rule_52_alias_qualifies_for_direct_match(self):
        """An alias occurring in title or snippet qualifies as a direct_match."""
        retrieved_works = [
            {
                "work_id": "corpus_2",
                "source": "openalex",
                "title": "Empirical Study of FA3 on Deep Neural Networks",
                "snippet": "Benchmarks demonstrating kernel speedups.",
            }
        ]

        status, _, matches = TechniqueGroundingService.evaluate_grounding_rule52(
            technique_name="FlashAttention-3",
            aliases=["FA3"],
            retrieved_works=retrieved_works,
        )

        assert status == "direct_match"
        assert matches[0]["match_type"] == "direct"

    def test_rule_52_related_only_when_name_missing_from_works(self):
        """Related works without explicit technique name or alias are classified as related_only."""
        retrieved_works = [
            {
                "work_id": "corpus_3",
                "source": "semantic_scholar",
                "title": "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
                "snippet": "We explore generating intermediate reasoning steps.",
            }
        ]

        status, explanation, matches = TechniqueGroundingService.evaluate_grounding_rule52(
            technique_name="Chain-of-Draft",
            aliases=["CoD Draft"],
            retrieved_works=retrieved_works,
        )

        assert status == "related_only"
        assert len(matches) == 1
        assert matches[0]["match_type"] == "related"
        assert RULE_52_RELATED_WORDING in explanation


@pytest.mark.django_db
class TestTechniqueGroundingService:
    """Verifies seeding, persistence, and card fallback integration."""

    def test_seed_default_techniques_is_idempotent(self):
        """Seeding techniques creates default canon and handles reruns cleanly."""
        created_1 = TechniqueGroundingService.seed_default_techniques()
        assert created_1 >= 5

        # Rerun is idempotent
        created_2 = TechniqueGroundingService.seed_default_techniques()
        assert created_2 == 0

        total_techs = TrendingTechnique.objects.count()
        assert total_techs >= 5

        # Verify FlashAttention-3
        fa3 = TrendingTechnique.objects.get(slug="flashattention-3")
        assert fa3.grounding_status == "direct_match"
        assert fa3.literature_links.count() >= 1

        # Verify Chain-of-Draft
        cod = TrendingTechnique.objects.get(slug="chain-of-draft")
        assert cod.grounding_status == "related_only"

        # Verify Sharding v3
        shard = TrendingTechnique.objects.get(slug="cognitive-memory-sharding-v3")
        assert shard.grounding_status == "no_literature_found"
        assert RULE_52_NO_LITERATURE_WORDING in shard.verdict_explanation

    def test_card_technique_grounding_and_cluster_fallback(self):
        """Design §9: When a card has no direct social mentions, surfaces technique-cluster fallback."""
        TechniqueGroundingService.seed_default_techniques()

        source = Source.objects.create(
            name="arXiv cs.AI",
            url="https://arxiv.org/abs/",
            trust_tier=1,
            fetch_method="api",
            publisher_relationship="independent",
        )
        raw_item = RawItem.objects.create(
            source=source,
            external_id="arxiv:2407.08608",
            title="Fast Attention Overlap on GPU",
            url="https://arxiv.org/abs/2407.08608",
            content_hash="hash_fa3_test_123",
            published_at=timezone.now(),
        )
        card = Card.objects.create(
            raw_item=raw_item,
            headline="Accelerating Attention via Asynchrony",
            summary_60s="• High throughput\n• Low precision",
            candidate_techniques=["FlashAttention-3", "FP8 GEMM"],
            tags=["flashattention", "gpu_hardware", "attention"],
            category="research",
            published_at=timezone.now(),
        )

        res = TechniqueGroundingService.get_grounding_for_card(card)
        assert res["has_technique"] is True
        assert res["technique"]["name"] == "FlashAttention-3"
        assert res["technique"]["grounding_status"] == "direct_match"
        assert len(res["technique"]["literature_links"]) >= 1

        # Fallback message is active because card has no direct social mentions
        assert "This paper isn't directly discussed yet, but FlashAttention-3 is trending" in res["fallback_message"]


@pytest.mark.django_db
class TestTechniqueGroundingAPI:
    """Verifies REST API endpoints for Step 7."""

    def test_trending_techniques_list_api(self):
        client = APIClient()
        response = client.get("/api/v1/research/techniques/trending/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 5
        assert len(data["results"]) >= 5

        # Check filter by status
        direct_resp = client.get("/api/v1/research/techniques/trending/?status=direct_match")
        assert direct_resp.status_code == 200
        for item in direct_resp.json()["results"]:
            assert item["grounding_status"] == "direct_match"

    def test_technique_detail_api(self):
        client = APIClient()
        response = client.get("/api/v1/research/techniques/grpo/")
        assert response.status_code == 200
        data = response.json()
        assert data["technique"]["slug"] == "grpo"
        assert data["technique"]["grounding_status"] == "direct_match"
        assert len(data["technique"]["literature_links"]) >= 1

    def test_card_grounding_api(self):
        TechniqueGroundingService.seed_default_techniques()
        source = Source.objects.create(
            name="arXiv cs.LG",
            url="https://arxiv.org/abs/",
            trust_tier=1,
            fetch_method="api",
            publisher_relationship="independent",
        )
        raw_item = RawItem.objects.create(
            source=source,
            external_id="arxiv:2106.09685",
            title="LoRA Fine Tuning",
            url="https://arxiv.org/abs/2106.09685",
            content_hash="hash_lora_test_789",
            published_at=timezone.now(),
        )
        card = Card.objects.create(
            raw_item=raw_item,
            headline="Parameter-Efficient Adaptation with LoRA",
            summary_60s="• Parameter efficient",
            candidate_techniques=["LoRA"],
            tags=["lora", "fine_tuning"],
            category="research",
            published_at=timezone.now(),
        )

        client = APIClient()
        response = client.get(f"/api/v1/research/cards/{card.id}/grounding/")
        assert response.status_code == 200
        data = response.json()
        assert data["has_technique"] is True
        assert data["technique"]["slug"] == "lora"
        assert data["technique"]["grounding_status"] == "direct_match"
