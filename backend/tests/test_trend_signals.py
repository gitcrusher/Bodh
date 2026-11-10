"""
tests/test_trend_signals.py

Tests for Step 6: Trend & Authenticity Signals (§6, §8, §16).

Verifies:
  1. Rule 40 — trust tier, validity signals, and trend signals are separate tables and never silently merged.
  2. TrendSeedAccount curation and idempotency across Reddit, Bluesky, Mastodon.
  3. Contextual trend signal generation and summary calculations.
  4. Resilient multi-platform aggregation (operates cleanly even without Reddit).
  5. REST API endpoints (GET /api/v1/research/cards/<id>/trends/ and GET /api/v1/research/trends/seeds/).
  6. Retention runner rule pruning old trend signals (>30 days).
"""

from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from research.retention import _prune_old_trend_signals
from research.models import (
    Card,
    PaperTrendSignal,
    PaperValiditySignal,
    RawItem,
    Source,
    TrendSeedAccount,
)
from research.trend_service import TrendService


@pytest.fixture
def sample_card(db):
    source = Source.objects.create(
        name="arXiv cs.CL",
        fetch_method="api",
        trust_tier=1,
        publisher_relationship="independent",
        rate_limit_policy={"calls_per_second": 1.0, "burst": 1},
        daily_request_cap=50,
    )
    raw = RawItem.objects.create(
        source=source,
        external_id="arxiv:2502.99999",
        url="https://arxiv.org/abs/2502.99999",
        title="DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning",
        raw_content="Abstract...",
        published_at=timezone.now(),
    )
    card = Card.objects.create(
        raw_item=raw,
        category="research",
        headline="DeepSeek-R1 reasoning model achieves state of the art via pure RL",
        summary_60s="The paper introduces DeepSeek-R1...",
        tags=["reasoning", "reinforcement_learning"],
        candidate_techniques=["Pure RL", "Distillation"],
        source_url="https://arxiv.org/abs/2502.99999",
        published_at=timezone.now(),
        is_primary_feed=True,
    )
    return card


@pytest.mark.django_db
class TestTrendSignals:
    def test_rule_40_structural_separation(self, sample_card):
        """Rule 40: Trust tier, validity signal, and trend signal are separate tables and never merged."""
        # 1. Source trust tier
        assert sample_card.raw_item.source.trust_tier == 1

        # 2. Validity signal in paper_validity_signals
        val = PaperValiditySignal.objects.create(
            card=sample_card,
            venue="arXiv preprint",
            venue_tier=3,
            affiliation_tier=1,
            data_source="arxiv_metadata",
        )
        assert val._meta.db_table == "paper_validity_signals"

        # 3. Trend signal in paper_trend_signals
        trend = PaperTrendSignal.objects.create(
            card=sample_card,
            platform="reddit",
            mention_count=520,
            engagement_score=1500.0,
            trending_reason="Massive upvotes on r/LocalLLaMA",
            sample_period="24h",
        )
        assert trend._meta.db_table == "paper_trend_signals"

        # Separate tables, no silent merging or field overwriting
        sample_card.refresh_from_db()
        assert sample_card.raw_item.source.trust_tier == 1
        assert sample_card.validity_signal.venue_tier == 3
        assert sample_card.trend_signals.count() == 1
        assert sample_card.trend_signals.first().mention_count == 520

    def test_seed_accounts_idempotency(self, db):
        """TrendSeedAccount stores curated accounts across platforms idempotently."""
        count1 = TrendService.seed_default_accounts()
        assert count1 >= 10
        total1 = TrendSeedAccount.objects.count()

        # Re-running seed does not duplicate rows
        count2 = TrendService.seed_default_accounts()
        assert count2 == 0
        assert TrendSeedAccount.objects.count() == total1

        platforms = set(TrendSeedAccount.objects.values_list("platform", flat=True))
        assert "reddit" in platforms
        assert "bluesky" in platforms
        assert "mastodon" in platforms

    def test_contextual_signal_generation_and_summary(self, sample_card):
        """Generates contextual trend signals and calculates consolidated summary."""
        signals = TrendService.generate_contextual_signals(sample_card)
        assert len(signals) >= 2

        summary = TrendService.get_card_trend_summary(sample_card)
        assert summary["is_trending"] is True
        assert summary["total_mentions"] > 500
        assert "reddit" in summary["platforms"]
        assert "bluesky" in summary["platforms"]
        assert len(summary["primary_reason"]) > 10

    def test_resilience_without_reddit(self, sample_card):
        """Design §8: Must function properly even if Reddit signals are absent or unavailable."""
        # Clear signals and add only Bluesky and Mastodon
        PaperTrendSignal.objects.filter(card=sample_card).delete()

        PaperTrendSignal.objects.create(
            card=sample_card,
            platform="bluesky",
            mention_count=350,
            engagement_score=800.0,
            trending_reason="Viral thread on #AI Bluesky feed",
        )
        PaperTrendSignal.objects.create(
            card=sample_card,
            platform="mastodon",
            mention_count=120,
            engagement_score=250.0,
            trending_reason="Discussed on sigmoid.social",
        )

        summary = TrendService.get_card_trend_summary(sample_card)
        assert summary["is_trending"] is True
        assert summary["total_mentions"] == 470
        assert "reddit" not in summary["platforms"]
        assert "bluesky" in summary["platforms"]
        assert "mastodon" in summary["platforms"]

    def test_card_trends_api_endpoints(self, sample_card):
        """GET /api/v1/research/cards/<id>/trends/ and /api/v1/research/trends/seeds/."""
        client = APIClient()

        # Seed accounts endpoint
        seed_resp = client.get("/api/v1/research/trends/seeds/")
        assert seed_resp.status_code == 200
        assert seed_resp.data["count"] >= 10

        # Card trends endpoint
        card_resp = client.get(f"/api/v1/research/cards/{sample_card.id}/trends/")
        assert card_resp.status_code == 200
        assert card_resp.data["card_id"] == sample_card.id
        assert "summary" in card_resp.data
        assert "signals" in card_resp.data
        assert len(card_resp.data["signals"]) >= 2

        # Verify feed serializer exposes trend_summary
        feed_resp = client.get("/api/v1/research/cards/")
        assert feed_resp.status_code == 200
        results = feed_resp.data["results"]
        matching = [c for c in results if c["id"] == sample_card.id]
        assert len(matching) == 1
        assert "trend_summary" in matching[0]
        assert matching[0]["trend_summary"]["is_trending"] is True

    def test_retention_rule_prunes_old_signals(self, sample_card):
        """Retention runner prunes signals older than 30 days while keeping fresh ones (§14.4)."""
        now = timezone.now()
        # Fresh signal (1 hour ago)
        fresh_sig = PaperTrendSignal.objects.create(
            card=sample_card,
            platform="reddit",
            mention_count=50,
            engagement_score=100.0,
            fetched_at=now - timedelta(hours=1),
        )
        # Old signal (35 days ago)
        old_sig = PaperTrendSignal.objects.create(
            card=sample_card,
            platform="bluesky",
            mention_count=20,
            engagement_score=40.0,
            fetched_at=now - timedelta(days=35),
        )

        assert PaperTrendSignal.objects.filter(pk=old_sig.pk).exists()
        assert PaperTrendSignal.objects.filter(pk=fresh_sig.pk).exists()

        # Execute retention rule
        _prune_old_trend_signals({})

        assert not PaperTrendSignal.objects.filter(pk=old_sig.pk).exists()
        assert PaperTrendSignal.objects.filter(pk=fresh_sig.pk).exists()
