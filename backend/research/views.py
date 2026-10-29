"""
research/views.py

DRF views for the research module feed API.

All routes are read-only except the report endpoint:
  GET  /api/v1/research/cards/           — paginated feed (newest first)
  GET  /api/v1/research/cards/{id}/      — single card with deep_dive_base
  POST /api/v1/research/cards/{id}/report/ — submit a content report
  GET  /api/v1/research/sources/         — list active sources (for health-check)

Pagination: cursor-based (see DRF settings). Scroll position is stable across
new cards being inserted, which is required for the reel-feed UX.
"""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import CursorPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from research.models import Card, ChatSession, Source
from research.serializers import (
    CardDetailSerializer,
    CardListSerializer,
    ChatSessionSerializer,
    ContentReportCreateSerializer,
    PaperChatRequestSerializer,
)

logger = logging.getLogger(__name__)


class CardCursorPagination(CursorPagination):
    """
    Cursor-paginated feed, newest card first.
    The cursor encodes published_at + id to give stable ordering even when
    new cards are inserted mid-scroll.
    """

    page_size = getattr(settings, "REST_FRAMEWORK", {}).get("PAGE_SIZE", 20)
    ordering = ("-published_at", "-id")
    cursor_query_param = "cursor"


class CardFeedView(APIView):
    """
    GET /api/v1/research/cards/

    Query params:
      category          — filter by card category (default: research)
      include_prior_art — if true, includes foundational/prior-art cards (default: false, fresh feed only)
      cursor            — opaque pagination cursor
    """

    def get(self, request: Request) -> Response:
        category = request.query_params.get("category", "research")
        include_prior_art = (
            request.query_params.get("include_prior_art", "false").lower() == "true"
        )
        qs = Card.objects.filter(category=category)
        if not include_prior_art:
            qs = qs.filter(is_primary_feed=True)

        qs = (
            qs.select_related("validity_signal")
            .prefetch_related("card_sources")
            .order_by("-published_at", "-id")
        )

        paginator = CardCursorPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = CardListSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = CardListSerializer(qs, many=True)
        return Response(serializer.data)


class CardDetailView(APIView):
    """GET /api/v1/research/cards/{id}/"""

    def get(self, request: Request, card_id: int) -> Response:
        try:
            card = (
                Card.objects.select_related("validity_signal")
                .prefetch_related("card_sources")
                .get(pk=card_id)
            )
        except Card.DoesNotExist:
            raise NotFound(f"Card {card_id} not found")

        # If deep_dive_base is null and this is the first open, trigger lazy generation.
        # For v1 we return null and the client shows a loading state;
        # async deep-dive generation is added in Step 3.
        serializer = CardDetailSerializer(card)
        return Response(serializer.data)


class CardReportView(APIView):
    """POST /api/v1/research/cards/{card_id}/report/"""

    def post(self, request: Request, card_id: int) -> Response:
        try:
            card = Card.objects.get(pk=card_id)
        except Card.DoesNotExist:
            raise NotFound(f"Card {card_id} not found")

        serializer = ContentReportCreateSerializer(
            data=request.data,
            context={"card": card},
        )
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        logger.info("CardReportView: report %d created for card %d", report.pk, card_id)
        return Response({"id": report.pk}, status=status.HTTP_201_CREATED)


class SourceListView(APIView):
    """GET /api/v1/research/sources/ — active sources (for admin / health checks)."""

    def get(self, request: Request) -> Response:
        sources = list(
            Source.objects.filter(active=True).values(
                "id", "name", "url", "trust_tier", "last_successful_run_at"
            )
        )
        return Response(sources)


# ---------------------------------------------------------------------------
# Step 3: Paper Chat Views
# ---------------------------------------------------------------------------


class PaperChatView(APIView):
    """
    POST /api/v1/research/cards/{card_id}/chat/

    Payload:
      message: str (max 2000 chars)
      session_id: int (optional, reuses existing conversation turn)
    """

    def post(self, request: Request, card_id: int) -> Response:
        try:
            card = Card.objects.select_related("raw_item").get(pk=card_id)
        except Card.DoesNotExist:
            raise NotFound(f"Card {card_id} not found")

        serializer = PaperChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]
        session_id = serializer.validated_data.get("session_id")

        session = None
        if session_id:
            try:
                session = ChatSession.objects.get(pk=session_id, card=card)
            except ChatSession.DoesNotExist:
                session = None

        from research.chat_engine import run_paper_chat

        user = request.user if request.user.is_authenticated else None
        res = run_paper_chat(
            card=card,
            user_message=message,
            session=session,
            user=user,
        )

        return Response(res, status=status.HTTP_200_OK)


class PaperChatHistoryView(APIView):
    """GET /api/v1/research/cards/{card_id}/chat/{session_id}/"""

    def get(self, request: Request, card_id: int, session_id: int) -> Response:
        try:
            session = (
                ChatSession.objects.prefetch_related("messages")
                .get(pk=session_id, card_id=card_id)
            )
        except ChatSession.DoesNotExist:
            raise NotFound(f"ChatSession {session_id} not found for card {card_id}")

        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)


class RelatedCardsView(APIView):
    """
    GET /api/v1/research/cards/{card_id}/related/
    Rule 56-58: Returns other cards related to this card.
    Prioritizes bound CardRelation dynamic links, seamlessly connecting
    new frontline research papers to prior-art foundational corpus cards.
    """

    def get(self, request: Request, card_id: int) -> Response:
        try:
            card = Card.objects.get(pk=card_id)
        except Card.DoesNotExist:
            raise NotFound(f"Card {card_id} not found")

        # 1. First check bound CardRelation links
        related_ids = list(
            card.outgoing_relations.values_list("target_card_id", flat=True)
        )
        if related_ids:
            qs = (
                Card.objects.filter(id__in=related_ids)
                .select_related("validity_signal")
                .prefetch_related("card_sources")
            )
            cards_by_id = {c.id: c for c in qs}
            ordered_cards = [cards_by_id[cid] for cid in related_ids if cid in cards_by_id]
            serializer = CardListSerializer(ordered_cards, many=True)
            return Response(serializer.data)

        # 2. Fallback to tags or candidate techniques
        qs = Card.objects.exclude(pk=card.pk)
        if card.tags:
            from django.db.models import Q
            tag_q = Q()
            for t in card.tags:
                tag_q |= Q(tags__icontains=t)
            qs = qs.filter(tag_q)
        elif card.candidate_techniques:
            from django.db.models import Q
            tech_q = Q()
            for t in card.candidate_techniques:
                tech_q |= Q(candidate_techniques__icontains=t)
            qs = qs.filter(tech_q)
        else:
            qs = qs.filter(category=card.category)

        qs = (
            qs.select_related("validity_signal")
            .prefetch_related("card_sources")
            .order_by("-published_at")[:10]
        )
        serializer = CardListSerializer(qs, many=True)
        return Response(serializer.data)


class DynamicPaperLinksView(APIView):
    """
    GET /api/v1/research/cards/{card_id}/links/
    Rule 56 & 57: Dynamic Research Links Flow.
    Returns dynamic research links connecting this paper to related corpus works.
    Auto-binds dynamic links on-demand if not already linked at ingest time.
    """

    def get(self, request: Request, card_id: int) -> Response:
        try:
            card = Card.objects.get(pk=card_id)
        except Card.DoesNotExist:
            raise NotFound(f"Card {card_id} not found")

        from research.paper_linker import get_dynamic_paper_links

        links = get_dynamic_paper_links(card, limit=10)
        topic = card.tags[0].replace("_", " ").title() if card.tags else (
            card.candidate_techniques[0].title() if card.candidate_techniques else "Related Research"
        )

        return Response({
            "card_id": card.id,
            "topic": topic,
            "links_count": len(links),
            "links": links,
        })



