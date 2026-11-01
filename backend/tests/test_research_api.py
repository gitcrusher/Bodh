"""
tests/test_research_api.py

Integration tests for research module DRF views:
- GET /api/v1/research/cards/ (cursor pagination, filtering)
- GET /api/v1/research/cards/{id}/ (detail view)
- POST /api/v1/research/cards/{id}/report/ (content report submission)
- GET /api/v1/research/sources/ (source list)
"""

from datetime import datetime, timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from research.models import Card, ContentReport, PaperValiditySignal, RawItem, Source


class TestResearchAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.source = Source.objects.create(
            name="arXiv CS.AI",
            url="https://arxiv.org/list/cs.AI/recent",
            knowledge_type=["research"],
            trust_tier=1,
            fetch_method="api",
            active=True,
        )
        self.raw_item = RawItem.objects.create(
            source=self.source,
            external_id="2310.99991",
            title="Attention Is All You Need",
            url="https://arxiv.org/abs/2310.99991",
            published_at=datetime.now(tz=timezone.utc),
            raw_content="Transformer architecture replaces recurrent layers with attention mechanisms.",
            content_hash="hash99991",
            status="processed",
        )
        self.card = Card.objects.create(
            raw_item=self.raw_item,
            category="research",
            headline="Attention Mechanism Revolutionizes NLP",
            summary_60s="• Introduces Transformer\n• Self-attention mechanism\n• SOTA performance",
            tags=["transformers", "nlp"],
            candidate_techniques=["self-attention"],
            source_url="https://arxiv.org/abs/2310.99991",
            published_at=datetime.now(tz=timezone.utc),
            needs_review=False,
        )
        self.validity = PaperValiditySignal.objects.create(
            card=self.card,
            venue="NeurIPS 2026",
            venue_tier=1,
            authors=["Ashish Vaswani", "Noam Shazeer"],
            affiliation_tier=1,
            data_source="arxiv_metadata",
        )

    def test_card_feed_returns_paginated_cards(self):
        response = self.client.get("/api/v1/research/cards/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("results", data)
        self.assertEqual(len(data["results"]), 1)
        item = data["results"][0]
        self.assertEqual(item["id"], self.card.pk)
        self.assertEqual(item["headline"], self.card.headline)
        self.assertIn("validity_signal", item)
        self.assertEqual(item["validity_signal"]["venue"], "NeurIPS 2026")

    def test_card_feed_filter_by_category(self):
        # Research category should return 1 item
        resp = self.client.get("/api/v1/research/cards/?category=research")
        self.assertEqual(len(resp.json()["results"]), 1)

        # Tools category should return 0 items
        resp_empty = self.client.get("/api/v1/research/cards/?category=tools")
        self.assertEqual(len(resp_empty.json()["results"]), 0)

    def test_card_detail_view(self):
        response = self.client.get(f"/api/v1/research/cards/{self.card.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["id"], self.card.pk)
        self.assertEqual(data["headline"], self.card.headline)
        self.assertEqual(data["tags"], ["transformers", "nlp"])
        self.assertEqual(data["source_url"], "https://arxiv.org/abs/2310.99991")

    def test_card_detail_not_found(self):
        response = self.client.get("/api/v1/research/cards/999999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_submit_content_report(self):
        payload = {
            "reason": "factual_error",
            "detail": "The claimed 99% accuracy is not supported by the paper abstract.",
        }
        response = self.client.post(
            f"/api/v1/research/cards/{self.card.pk}/report/",
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ContentReport.objects.filter(card=self.card).exists())
        report = ContentReport.objects.get(card=self.card)
        self.assertEqual(report.reason, "factual_error")
        self.assertIn("claimed 99%", report.detail)

    def test_source_list_view(self):
        response = self.client.get("/api/v1/research/sources/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "arXiv CS.AI")

    def test_related_cards_view(self):
        raw_item_2 = RawItem.objects.create(
            source=self.source,
            external_id="2310.99992",
            title="Transformer Scaling Laws",
            url="https://arxiv.org/abs/2310.99992",
            published_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
            status="processed",
        )
        card_2 = Card.objects.create(
            raw_item=raw_item_2,
            category="research",
            headline="Empirical Analysis of Scaling in Transformers",
            summary_60s="• Examines power law scaling\n• Evaluates token compute tradeoffs",
            tags=["transformers", "scaling"],
            source_url="https://arxiv.org/abs/2310.99992",
            published_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
        )

        resp = self.client.get(f"/api/v1/research/cards/{self.card.pk}/related/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], card_2.pk)
        self.assertEqual(data[0]["headline"], card_2.headline)

        resp_detail = self.client.get(f"/api/v1/research/cards/{self.card.pk}/")
        detail_data = resp_detail.json()
        self.assertEqual(detail_data["related_count"], 1)
        self.assertEqual(detail_data["related_topic"], "Transformers")
        self.assertEqual(len(detail_data["related_preview"]), 1)

