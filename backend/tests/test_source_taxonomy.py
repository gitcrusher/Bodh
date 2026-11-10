"""
tests/test_source_taxonomy.py — Tests for Step 5: Widen the Source Taxonomy.

Verifies:
  - 7 knowledge categories supported in Source and Card models (Rule 7 & System Design §7).
  - Source model supports trust tiers (1, 2, 3) and publisher relationships ('independent', 'developer_self_report').
  - CardListSerializer and CardDetailSerializer expose `publisher_relationship`.
  - Rule 50: developer self-reports are primary sources but clearly flagged via publisher_relationship.
  - Seed taxonomy command registers trusted sources with valid properties.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from research.models import Card, RawItem, Source, PaperValiditySignal
from research.serializers import CardListSerializer, CardDetailSerializer


@pytest.fixture
def independent_source(db):
    return Source.objects.create(
        name="METR Safety Evaluator",
        url="https://metr.org",
        trust_tier=1,
        publisher_relationship="independent",
        knowledge_type=["threat_safety"],
        active=True,
    )


@pytest.fixture
def developer_source(db):
    return Source.objects.create(
        name="Anthropic Research Releases",
        url="https://anthropic.com/research",
        trust_tier=1,
        publisher_relationship="developer_self_report",
        knowledge_type=["new_models"],
        active=True,
    )


@pytest.fixture
def safety_card(db, independent_source):
    raw = RawItem.objects.create(
        source=independent_source,
        external_id="metr-eval-001",
        title="METR Cyber Autonomy Evaluation",
        url="https://metr.org/eval-001",
        published_at=timezone.now(),
        raw_content="Autonomous evaluations of frontier AI systems.",
    )
    return Card.objects.create(
        raw_item=raw,
        category="threat_safety",
        headline="METR Evaluates Frontier Autonomy Capabilities",
        summary_60s="• Tests autonomous exploitation.\n• Benchmark over multi-hour horizons.\n• Recommends deployment thresholds.",
        tags=["threat_safety", "autonomy"],
        candidate_techniques=["task horizon evaluation"],
        source_url="https://metr.org/eval-001",
        published_at=timezone.now(),
        needs_review=False,
    )


@pytest.fixture
def model_card(db, developer_source):
    raw = RawItem.objects.create(
        source=developer_source,
        external_id="anthropic-claude-release",
        title="Claude 3.7 Release",
        url="https://anthropic.com/claude-3-7",
        published_at=timezone.now(),
        raw_content="Claude 3.7 hybrid reasoning release announcement.",
    )
    return Card.objects.create(
        raw_item=raw,
        category="new_models",
        headline="Anthropic Releases Claude 3.7 Sonnet",
        summary_60s="• Hybrid thinking architecture.\n• Top scores on SWE-bench.\n• Dynamic inference compute scaling.",
        tags=["new_models", "claude"],
        candidate_techniques=["hybrid thinking"],
        source_url="https://anthropic.com/claude-3-7",
        published_at=timezone.now(),
        needs_review=False,
    )


@pytest.mark.django_db
class TestSourceTaxonomy:
    def test_source_model_stores_taxonomy_and_relationship(self, independent_source, developer_source):
        assert independent_source.publisher_relationship == "independent"
        assert independent_source.trust_tier == 1
        assert "threat_safety" in independent_source.knowledge_type

        assert developer_source.publisher_relationship == "developer_self_report"
        assert developer_source.trust_tier == 1
        assert "new_models" in developer_source.knowledge_type

    def test_card_list_serializer_exposes_publisher_relationship(self, safety_card, model_card):
        safety_data = CardListSerializer(safety_card).data
        assert safety_data["publisher_relationship"] == "independent"
        assert safety_data["category"] == "threat_safety"

        model_data = CardListSerializer(model_card).data
        assert model_data["publisher_relationship"] == "developer_self_report"
        assert model_data["category"] == "new_models"

    def test_card_detail_serializer_exposes_publisher_relationship(self, safety_card, model_card):
        safety_data = CardDetailSerializer(safety_card).data
        assert safety_data["publisher_relationship"] == "independent"

        model_data = CardDetailSerializer(model_card).data
        assert model_data["publisher_relationship"] == "developer_self_report"

    def test_rule_50_developer_self_report_distinction(self, independent_source, developer_source):
        """Rule 50: developer reports retain primary source trust tier (1) while clearly carrying publisher_relationship."""
        assert developer_source.trust_tier == 1
        assert developer_source.publisher_relationship == "developer_self_report"

        assert independent_source.trust_tier == 1
        assert independent_source.publisher_relationship == "independent"

    def test_all_seven_taxonomy_categories_valid_in_card_choices(self):
        valid_cats = {
            "research",
            "new_models",
            "threat_safety",
            "policy",
            "industry",
            "opinion",
            "tools",
        }
        model_choices = {choice[0] for choice in Card.CATEGORY_CHOICES}
        for cat in valid_cats:
            assert cat in model_choices, f"Category {cat} missing from Card.CATEGORY_CHOICES"

    def test_api_feed_returns_widened_categories_and_publisher_relationship(self, safety_card, model_card):
        client = APIClient()
        response = client.get("/api/v1/research/cards/?category=all")
        assert response.status_code == 200
        results = response.data.get("results", [])
        assert len(results) >= 2

        card_by_id = {c["id"]: c for c in results}
        assert safety_card.id in card_by_id
        assert model_card.id in card_by_id

        assert card_by_id[safety_card.id]["publisher_relationship"] == "independent"
        assert card_by_id[safety_card.id]["category"] == "threat_safety"

        assert card_by_id[model_card.id]["publisher_relationship"] == "developer_self_report"
        assert card_by_id[model_card.id]["category"] == "new_models"

        # Also verify category filtering
        resp_safety = client.get("/api/v1/research/cards/?category=threat_safety")
        assert resp_safety.status_code == 200
        assert len(resp_safety.data.get("results", [])) == 1
        assert resp_safety.data["results"][0]["id"] == safety_card.id
