"""
tests/test_research_pipeline.py

Unit tests for the Step 1 research pipeline.

Coverage:
  - persist_node: writes new RawItem rows; skips duplicate external_id
  - triage_node: accepted → in triage_ids; rejected → status=discarded
  - budget_node: items beyond daily budget are cut
  - summarize_node: happy path writes Card; extractive fallback on FailedGenerationError
  - number_check_node: marks card needs_review on unfaithful summary
  - validity_node: writes PaperValiditySignal row
  - report_node: writes run_summary and updates last_successful_run_at
  - graph smoke-test: dry-run returns a run_summary without crashing

All tests run on SQLite. LLM calls are mocked; embedding calls are patched
to return zero vectors so sentence-transformers is never loaded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase

from research.models import Card, CardSource, ContentReport, PaperValiditySignal, RawItem, Source
from research.pipeline.nodes import (
    budget_node,
    number_check_node,
    persist_node,
    report_node,
    summarize_node,
    triage_node,
    validity_node,
)
from research.pipeline.state import PipelineState

ZERO_VEC = [0.0] * 384


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_source(**kwargs) -> Source:
    defaults = {
        "name": "arXiv cs.AI",
        "url": "https://arxiv.org",
        "fetch_method": "api",
        "trust_tier": 1,
        "daily_request_cap": 500,
    }
    defaults.update(kwargs)
    return Source.objects.create(**defaults)


def raw_item_dict(external_id: str = "2310.00001") -> dict:
    return {
        "external_id": external_id,
        "title": "Test Paper: Attention Is All You Need",
        "url": f"https://arxiv.org/abs/{external_id}",
        "published_at": datetime(2024, 1, 15, tzinfo=timezone.utc),
        "raw_content": "We present a new model that achieves 95% accuracy on benchmark X.",
        "content_hash": f"hash_{external_id}",
        "authors": ["Alice", "Bob"],
    }


def make_raw_item(source: Source, external_id: str = "2310.00001") -> RawItem:
    return RawItem.objects.create(
        source=source,
        external_id=external_id,
        title="Test Paper",
        url=f"https://arxiv.org/abs/{external_id}",
        published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        raw_content="Abstract text about transformers and 95% accuracy on benchmark X.",
        status="new",
    )


def make_card(source: Source, external_id: str = "2310.00099") -> Card:
    item = RawItem.objects.create(
        source=source,
        external_id=external_id,
        title="Existing Paper",
        url=f"https://arxiv.org/abs/{external_id}",
        published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        status="processed",
    )
    return Card.objects.create(
        raw_item=item,
        category="research",
        headline="Existing card headline",
        summary_60s="• Existing summary",
        tags=["nlp"],
        source_url=item.url,
        published_at=item.published_at,
    )


# ---------------------------------------------------------------------------
# persist_node
# ---------------------------------------------------------------------------


class TestPersistNode(TestCase):
    def test_writes_new_raw_items(self):
        source = make_source()
        state: PipelineState = {
            "source_id": source.pk,
            "raw_items_fetched": [raw_item_dict("2310.00001"), raw_item_dict("2310.00002")],
            "errors": [],
        }
        result = persist_node(state)
        self.assertEqual(len(result["raw_item_ids"]), 2)
        self.assertEqual(RawItem.objects.count(), 2)

    def test_skips_duplicate_external_id(self):
        source = make_source()
        # Pre-create one item
        RawItem.objects.create(
            source=source,
            external_id="2310.00001",
            title="existing",
            url="https://arxiv.org/abs/2310.00001",
            published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )
        state: PipelineState = {
            "source_id": source.pk,
            "raw_items_fetched": [raw_item_dict("2310.00001")],  # duplicate
            "errors": [],
        }
        result = persist_node(state)
        self.assertEqual(result["raw_item_ids"], [])
        self.assertEqual(RawItem.objects.count(), 1)  # no new row


# ---------------------------------------------------------------------------
# triage_node
# ---------------------------------------------------------------------------


class TestTriageNode(TestCase):
    @patch("research.pipeline.nodes._ledger.check", return_value=False)
    @patch("research.pipeline.nodes._ledger.mark_done")
    @patch("research.pipeline.nodes.run_step", return_value=("", {"accept": True}))
    def test_accepted_item_passes_through(self, mock_run, mock_done, mock_check):
        source = make_source()
        item = make_raw_item(source, "2310.00010")
        state: PipelineState = {
            "dedup_ids": [item.pk],
            "token_budget": 500_000,
            "tokens_used": 0,
            "errors": [],
        }
        result = triage_node(state)
        self.assertIn(item.pk, result["triage_ids"])

    @patch("research.pipeline.nodes._ledger.check", return_value=False)
    @patch("research.pipeline.nodes._ledger.mark_done")
    @patch("research.pipeline.nodes.run_step", return_value=("", {"accept": False}))
    def test_rejected_item_is_discarded(self, mock_run, mock_done, mock_check):
        source = make_source()
        item = make_raw_item(source, "2310.00011")
        state: PipelineState = {
            "dedup_ids": [item.pk],
            "token_budget": 500_000,
            "tokens_used": 0,
            "errors": [],
        }
        result = triage_node(state)
        self.assertNotIn(item.pk, result["triage_ids"])
        item.refresh_from_db()
        self.assertEqual(item.status, "discarded")


# ---------------------------------------------------------------------------
# budget_node
# ---------------------------------------------------------------------------


class TestBudgetNode(TestCase):
    def test_respects_daily_budget(self):
        state: PipelineState = {"triage_ids": [1, 2, 3, 4, 5], "errors": []}
        with self.settings(DAILY_CARD_BUDGET=3):
            result = budget_node(state)
        self.assertEqual(len(result["budgeted_ids"]), 3)

    def test_all_items_pass_within_budget(self):
        state: PipelineState = {"triage_ids": [1, 2], "errors": []}
        with self.settings(DAILY_CARD_BUDGET=50):
            result = budget_node(state)
        self.assertEqual(len(result["budgeted_ids"]), 2)


# ---------------------------------------------------------------------------
# summarize_node
# ---------------------------------------------------------------------------

_GOOD_SUMMARY = {
    "headline": "New model beats baseline on benchmark X",
    "summary_60s": "• Introduces Transformer-XL\n• Achieves 95% on X\n• Open-sourced",
    "tags": ["transformers", "nlp"],
    "candidate_techniques": ["attention", "LoRA"],
    "is_priority": False,
}


class TestSummarizeNode(TestCase):
    @patch("research.pipeline.nodes._ledger.check", return_value=False)
    @patch("research.pipeline.nodes._ledger.mark_done")
    @patch("research.pipeline.nodes.embedding_service.embed", return_value=ZERO_VEC)
    @patch("research.pipeline.nodes.run_step", return_value=("", _GOOD_SUMMARY))
    def test_happy_path_writes_card(self, mock_run, mock_embed, mock_done, mock_check):
        source = make_source()
        item = make_raw_item(source, "2310.00020")
        state: PipelineState = {
            "budgeted_ids": [item.pk],
            "token_budget": 500_000,
            "tokens_used": 0,
            "errors": [],
        }
        result = summarize_node(state)
        self.assertEqual(len(result["card_ids"]), 1)
        card = Card.objects.get(pk=result["card_ids"][0])
        self.assertEqual(card.headline, _GOOD_SUMMARY["headline"])
        self.assertFalse(card.needs_review)

    @patch("research.pipeline.nodes._ledger.check", return_value=False)
    @patch("research.pipeline.nodes._ledger.mark_done")
    @patch("research.pipeline.nodes.embedding_service.embed", return_value=ZERO_VEC)
    @patch("research.pipeline.nodes.run_step")
    def test_extractive_fallback_on_failed_generation(self, mock_run, mock_embed, mock_done, mock_check):
        from research.pipeline.nodes import FailedGenerationError

        mock_run.side_effect = FailedGenerationError("schema failed")
        source = make_source()
        item = make_raw_item(source, "2310.00021")
        state: PipelineState = {
            "budgeted_ids": [item.pk],
            "token_budget": 500_000,
            "tokens_used": 0,
            "errors": [],
        }
        result = summarize_node(state)
        self.assertEqual(len(result["card_ids"]), 1)
        card = Card.objects.get(pk=result["card_ids"][0])
        self.assertTrue(card.needs_review)


# ---------------------------------------------------------------------------
# number_check_node
# ---------------------------------------------------------------------------


class TestNumberCheckNode(TestCase):
    @patch("research.pipeline.nodes._ledger.check", return_value=False)
    @patch("research.pipeline.nodes._ledger.mark_done")
    @patch(
        "research.pipeline.nodes.run_step",
        return_value=("", {"faithful": False, "mismatches": ["99% not in abstract"]}),
    )
    def test_unfaithful_summary_marks_needs_review(self, mock_run, mock_done, mock_check):
        source = make_source()
        card = make_card(source, "2310.00030")
        state: PipelineState = {
            "card_ids": [card.pk],
            "token_budget": 500_000,
            "tokens_used": 0,
            "errors": [],
        }
        number_check_node(state)
        card.refresh_from_db()
        self.assertTrue(card.needs_review)

    @patch("research.pipeline.nodes._ledger.check", return_value=False)
    @patch("research.pipeline.nodes._ledger.mark_done")
    @patch("research.pipeline.nodes.run_step", return_value=("", {"faithful": True}))
    def test_faithful_summary_stays_clean(self, mock_run, mock_done, mock_check):
        source = make_source()
        card = make_card(source, "2310.00031")
        state: PipelineState = {
            "card_ids": [card.pk],
            "token_budget": 500_000,
            "tokens_used": 0,
            "errors": [],
        }
        number_check_node(state)
        card.refresh_from_db()
        self.assertFalse(card.needs_review)


# ---------------------------------------------------------------------------
# validity_node
# ---------------------------------------------------------------------------


class TestValidityNode(TestCase):
    def test_writes_validity_signal(self):
        source = make_source()
        card = make_card(source, "2310.00040")
        state: PipelineState = {"card_ids": [card.pk], "errors": []}
        validity_node(state)
        self.assertTrue(PaperValiditySignal.objects.filter(card=card).exists())
        sig = PaperValiditySignal.objects.get(card=card)
        self.assertEqual(sig.venue, "arXiv preprint")
        self.assertEqual(sig.venue_tier, 3)

    def test_idempotent_does_not_duplicate(self):
        source = make_source()
        card = make_card(source, "2310.00041")
        state: PipelineState = {"card_ids": [card.pk], "errors": []}
        validity_node(state)
        validity_node(state)  # second call — should be idempotent
        self.assertEqual(PaperValiditySignal.objects.filter(card=card).count(), 1)


# ---------------------------------------------------------------------------
# report_node
# ---------------------------------------------------------------------------


class TestReportNode(TestCase):
    def test_writes_run_summary(self):
        source = make_source()
        state: PipelineState = {
            "source_id": source.pk,
            "card_ids": [1, 2, 3],
            "tokens_used": 12345,
            "errors": [],
        }
        result = report_node(state)
        summary = result["run_summary"]
        self.assertEqual(summary["cards_written"], 3)
        self.assertEqual(summary["tokens_used"], 12345)
        self.assertIn("finished_at", summary)

    def test_updates_last_successful_run_at_on_no_errors(self):
        source = make_source()
        self.assertIsNone(source.last_successful_run_at)
        state: PipelineState = {
            "source_id": source.pk,
            "card_ids": [1],
            "tokens_used": 0,
            "errors": [],
        }
        report_node(state)
        source.refresh_from_db()
        self.assertIsNotNone(source.last_successful_run_at)


# ---------------------------------------------------------------------------
# Full graph smoke-test (dry-run)
# ---------------------------------------------------------------------------


class TestResearchGraphSmoke(TestCase):
    """
    Smoke-test: run the compiled LangGraph in dry-run mode.
    No HTTP calls, no LLM calls — just verifies the graph compiles and runs
    without crashing, returning a run_summary.
    """

    def test_dry_run_graph_returns_summary(self):
        source = make_source()
        from research.graph import run_daily_research

        # Patch feature flag to always be enabled in tests
        with patch("core.flags.feature_flags.is_enabled", return_value=True):
            summary = run_daily_research(source.pk, dry_run=True)

        self.assertIsInstance(summary, dict)
        # dry_run → no items fetched → 0 cards written
        self.assertEqual(summary.get("cards_written", 0), 0)
        self.assertIn("finished_at", summary)
