"""
research/serializers.py

DRF serializers for the research module's read-only feed API.

Endpoints served:
  GET /api/v1/research/cards/        — paginated card feed (cursor-paginated)
  GET /api/v1/research/cards/{id}/   — single card detail
  POST /api/v1/research/cards/{id}/report/  — submit a content report
"""

from rest_framework import serializers

from research.models import (
    Card,
    CardRelation,
    CardSource,
    ChatMessage,
    ChatSession,
    ContentReport,
    PaperChatChunk,
    PaperValiditySignal,
)


class CardSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardSource
        fields = ["source_url", "discovered_at"]


class ValiditySignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperValiditySignal
        fields = ["venue", "venue_tier", "affiliation_tier", "data_source", "fetched_at"]


class CardListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the paginated feed — excludes deep_dive_base."""

    validity_signal = ValiditySignalSerializer(read_only=True)
    card_sources = CardSourceSerializer(many=True, read_only=True)
    related_count = serializers.SerializerMethodField()
    related_topic = serializers.SerializerMethodField()
    related_preview = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = [
            "id",
            "category",
            "headline",
            "summary_60s",
            "tags",
            "source_url",
            "image_url",
            "published_at",
            "needs_review",
            "is_primary_feed",
            "created_at",
            "validity_signal",
            "card_sources",
            "related_count",
            "related_topic",
            "related_preview",
        ]

    def get_related_topic(self, obj: Card) -> str:
        if obj.tags:
            tag = obj.tags[0]
            return tag.replace("_", " ").title()
        if obj.candidate_techniques:
            return obj.candidate_techniques[0].title()
        return "Related Research"

    def get_related_count(self, obj: Card) -> int:
        rel_count = obj.outgoing_relations.count()
        if rel_count > 0:
            return rel_count
        if not obj.tags:
            return 0
        tag = obj.tags[0]
        return Card.objects.filter(tags__icontains=tag).exclude(pk=obj.pk).count()

    def get_related_preview(self, obj: Card) -> list[dict]:
        relations = list(
            obj.outgoing_relations.select_related("target_card")[:2]
        )
        if relations:
            return [
                {"id": r.target_card.id, "headline": r.target_card.headline, "category": r.target_card.category}
                for r in relations
            ]
        if not obj.tags:
            return []
        tag = obj.tags[0]
        siblings = (
            Card.objects.filter(tags__icontains=tag)
            .exclude(pk=obj.pk)
            .order_by("-published_at")[:2]
        )
        return [
            {"id": s.id, "headline": s.headline, "category": s.category}
            for s in siblings
        ]


class CardDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer — includes deep_dive_base (may be null)."""

    validity_signal = ValiditySignalSerializer(read_only=True)
    card_sources = CardSourceSerializer(many=True, read_only=True)
    related_count = serializers.SerializerMethodField()
    related_topic = serializers.SerializerMethodField()
    related_preview = serializers.SerializerMethodField()

    class Meta:
        model = Card
        fields = [
            "id",
            "category",
            "headline",
            "summary_60s",
            "tags",
            "candidate_techniques",
            "deep_dive_base",
            "source_url",
            "image_url",
            "published_at",
            "needs_review",
            "is_primary_feed",
            "created_at",
            "validity_signal",
            "card_sources",
            "related_count",
            "related_topic",
            "related_preview",
        ]

    def get_related_topic(self, obj: Card) -> str:
        if obj.tags:
            tag = obj.tags[0]
            return tag.replace("_", " ").title()
        if obj.candidate_techniques:
            return obj.candidate_techniques[0].title()
        return "Related Research"

    def get_related_count(self, obj: Card) -> int:
        rel_count = obj.outgoing_relations.count()
        if rel_count > 0:
            return rel_count
        if not obj.tags:
            return 0
        tag = obj.tags[0]
        return Card.objects.filter(tags__icontains=tag).exclude(pk=obj.pk).count()

    def get_related_preview(self, obj: Card) -> list[dict]:
        relations = list(
            obj.outgoing_relations.select_related("target_card")[:2]
        )
        if relations:
            return [
                {"id": r.target_card.id, "headline": r.target_card.headline, "category": r.target_card.category}
                for r in relations
            ]
        if not obj.tags:
            return []
        tag = obj.tags[0]
        siblings = (
            Card.objects.filter(tags__icontains=tag)
            .exclude(pk=obj.pk)
            .order_by("-published_at")[:2]
        )
        return [
            {"id": s.id, "headline": s.headline, "category": s.category}
            for s in siblings
        ]


class ContentReportCreateSerializer(serializers.ModelSerializer):
    """Write-only serializer for reader-submitted issue reports."""

    class Meta:
        model = ContentReport
        fields = ["reason", "detail"]

    def create(self, validated_data):
        card = self.context["card"]
        return ContentReport.objects.create(card=card, **validated_data)


# ---------------------------------------------------------------------------
# Step 3: Paper Chat Serializers
# ---------------------------------------------------------------------------


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "role", "content", "citations", "created_at"]


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = ["id", "card_id", "scope_type", "mode", "started_at", "messages"]


class PaperChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000, required=True)
    session_id = serializers.IntegerField(required=False, allow_null=True)


# ---------------------------------------------------------------------------
# Step 3+ : Dynamic Paper Link Serializers (Rule 56 & 57)
# ---------------------------------------------------------------------------


class DynamicPaperLinkSerializer(serializers.Serializer):
    """
    Serializer for dynamic research links flowing between papers.
    Used by the client's reusable DynamicPaperLinkTile components.
    """

    id = serializers.IntegerField()
    relation_type = serializers.CharField()
    relation_label = serializers.CharField()
    similarity_score = serializers.FloatField()
    created_at = serializers.CharField(allow_null=True, required=False)
    target_card_id = serializers.IntegerField()
    target_headline = serializers.CharField()
    target_summary_60s = serializers.CharField()
    target_category = serializers.CharField()
    target_source_url = serializers.CharField()
    target_image_url = serializers.CharField(allow_null=True, required=False)
    target_published_at = serializers.CharField(allow_null=True, required=False)
    target_tags = serializers.ListField(child=serializers.CharField(), required=False)
    target_techniques = serializers.ListField(child=serializers.CharField(), required=False)


