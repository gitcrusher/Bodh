"""
learning/views.py — DRF API views for the learning module (Step 2)

Endpoints under /api/v1/learning/:
  GET  /topics/                   — list seeded quiz topics
  GET  /profile/                  — authenticated user's learner profiles (all topics)
  POST /quiz/start/               — create a new QuizSession for a topic
  GET  /quiz/<session_id>/        — current session state + next question
  POST /quiz/<session_id>/answer/ — submit one answer
  POST /quiz/<session_id>/swap/   — swap unanswered questions (backgrounded)
  GET  /deep-dive/<card_id>/      — level-adaptive deep-dive for a card

Auth: all endpoints require login (IsAuthenticated).
Rule 30: this module writes only its own tables.
"""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import QuizSession, SessionState, Topic, KnowledgeLevel
from .quiz_engine import start_session, submit_answer, swap_unanswered_questions
from .serializers import (
    AnswerSubmitSerializer,
    DeepDiveResponseSerializer,
    LearnerProfileSerializer,
    QuizQuestionSerializer,
    QuizSessionSerializer,
    TopicSerializer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Topics
# ---------------------------------------------------------------------------

class TopicListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        topics = Topic.objects.filter(is_seeded=True)
        return Response(TopicSerializer(topics, many=True).data)


# ---------------------------------------------------------------------------
# Learner Profile
# ---------------------------------------------------------------------------

class LearnerProfileView(APIView):
    """Return the authenticated user's calibrated level across all topics."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        from .models import LearnerProfile
        profiles = LearnerProfile.objects.filter(user=request.user).select_related("topic")
        return Response(LearnerProfileSerializer(profiles, many=True).data)


# ---------------------------------------------------------------------------
# Quiz session: start
# ---------------------------------------------------------------------------

class QuizStartView(APIView):
    """POST {"topic_slug": "transformers"} → creates and returns a new session."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        topic_slug = request.data.get("topic_slug")
        if not topic_slug:
            return Response({"detail": "topic_slug is required."}, status=status.HTTP_400_BAD_REQUEST)

        topic = get_object_or_404(Topic, slug=topic_slug, is_seeded=True)

        # Abandon any active session for this topic
        QuizSession.objects.filter(
            user=request.user, topic=topic, state=SessionState.ACTIVE
        ).update(state=SessionState.ABANDONED)

        session = start_session(user=request.user, topic=topic)

        if not session.question_ids:
            return Response(
                {"detail": "No questions available for this topic yet. Check back soon."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        session_data = QuizSessionSerializer(session).data
        # Include first question
        first_q = _get_question(session, 0)
        session_data["current_question"] = first_q
        return Response(session_data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Quiz session: detail + answer
# ---------------------------------------------------------------------------

class QuizSessionDetailView(APIView):
    """GET current session state + current question."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, session_id: int) -> Response:
        session = get_object_or_404(QuizSession, pk=session_id, user=request.user)
        data = QuizSessionSerializer(session).data
        data["current_question"] = _get_question(session, session.current_index)
        return Response(data)


class QuizAnswerView(APIView):
    """POST an answer to the current question."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, session_id: int) -> Response:
        session = get_object_or_404(QuizSession, pk=session_id, user=request.user)

        if session.state != SessionState.ACTIVE:
            return Response(
                {"detail": f"Session is {session.state}, not active."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = AnswerSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        try:
            result = submit_answer(
                session=session,
                question_id=vd["question_id"],
                chosen_index=vd["chosen_original_index"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Include next question if session not ended
        if not result["session_ended"] and result.get("next_question_id"):
            next_q_idx = session.question_ids.index(result["next_question_id"])
            result["next_question"] = _get_question(session, next_q_idx)
        else:
            result["next_question"] = None

        # Refresh session for serialisation
        session.refresh_from_db()
        result["session"] = QuizSessionSerializer(session).data

        return Response(result)


# ---------------------------------------------------------------------------
# Swap unanswered questions (backgrounded — design.md §7)
# ---------------------------------------------------------------------------

class QuizSwapView(APIView):
    """POST — swap unanswered questions after backgrounding."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, session_id: int) -> Response:
        session = get_object_or_404(QuizSession, pk=session_id, user=request.user)
        session = swap_unanswered_questions(session)
        data = QuizSessionSerializer(session).data
        data["current_question"] = _get_question(session, session.current_index)
        return Response(data)


# ---------------------------------------------------------------------------
# Level-adaptive deep-dive
# ---------------------------------------------------------------------------

class DeepDiveView(APIView):
    """GET /deep-dive/<card_id>/?topic=<slug>

    Reads the user's quiz-calibrated level for the topic and returns a
    pitched deep-dive.  Falls back to 'familiar' if no quiz taken (design.md §4).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, card_id: int) -> Response:
        from .deep_dive import get_deep_dive
        from research.models import Card  # cross-module read (permitted — Rule 29 prohibits writes)

        topic_slug = request.query_params.get("topic", "")
        force_level = request.query_params.get("level")  # admin / test override

        try:
            card = Card.objects.get(pk=card_id)
        except Card.DoesNotExist:
            return Response({"detail": "Card not found."}, status=status.HTTP_404_NOT_FOUND)

        # Build source text from card fields
        source_text = "\n\n".join(filter(None, [
            card.headline,
            "\n".join(card.bullet_points) if hasattr(card, "bullet_points") else "",
        ]))

        try:
            result = get_deep_dive(
                user=request.user,
                card_id=card_id,
                topic_slug=topic_slug or "transformers",
                source_text=source_text,
                card_headline=card.headline,
                force_level=force_level,
            )
        except Exception as exc:
            logger.exception("Deep-dive generation error for card %s: %s", card_id, exc)
            return Response(
                {"detail": "Deep-dive temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(DeepDiveResponseSerializer(result).data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_question(session: QuizSession, index: int) -> dict | None:
    """Return the serialised question at position index, or None if exhausted."""
    if index >= len(session.question_ids):
        return None
    from .models import QuizQuestion
    try:
        q = QuizQuestion.objects.get(pk=session.question_ids[index])
        return QuizQuestionSerializer(q).data
    except QuizQuestion.DoesNotExist:
        return None
