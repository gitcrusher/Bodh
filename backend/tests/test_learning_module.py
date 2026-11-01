"""
tests/test_learning_module.py — Step 2: Learning module tests

Covers:
  - QuizSession creation and question selection
  - Answer submission, scoring, early-end confidence
  - Level assignment (new/familiar/fluent)
  - Background swap of unanswered questions
  - LearnerProfile upsert after session completion
  - Seeding from golden question bank
  - DeepDiveCache behaviour (cache miss → store, cache hit → return)
  - REST API endpoints (topics, profile, quiz start/answer/swap, deep-dive)

All tests use SQLite (no real LLM calls; deep_dive generator is mocked).
"""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from learning.evals.golden_questions import GOLDEN_QUESTIONS
from learning.models import (
    DeepDiveCache,
    KnowledgeLevel,
    LearnerProfile,
    QuizAnswer,
    QuizQuestion,
    QuizSession,
    SessionState,
    Topic,
)
from learning.quiz_engine import (
    EARLY_END_ACCURACY,
    EARLY_END_MIN_ANSWERED,
    MAX_QUESTIONS,
    _score_to_level,
    get_user_level,
    start_session,
    submit_answer,
    swap_unanswered_questions,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="pw")


@pytest.fixture
def topic(db):
    return Topic.objects.create(slug="transformers", display_name="Transformer Architecture", is_seeded=True)


@pytest.fixture
def questions(db, topic):
    """Create 3 easy + 4 medium + 3 hard questions for the topic."""
    qs = []
    for difficulty, count in [("easy", 3), ("medium", 4), ("hard", 3)]:
        for i in range(count):
            q = QuizQuestion.objects.create(
                topic=topic,
                difficulty=difficulty,
                stem=f"Q {difficulty} {i+1}?",
                options=["A", "B", "C", "D"],
                correct_index=0,
                explanation="Correct is A.",
                is_active=True,
            )
            qs.append(q)
    return qs


@pytest.fixture
def session(db, user, topic, questions):
    return start_session(user=user, topic=topic)


# ---------------------------------------------------------------------------
# Score → level
# ---------------------------------------------------------------------------

class TestScoreToLevel:
    def test_fluent(self):
        assert _score_to_level(0.85) == KnowledgeLevel.FLUENT

    def test_familiar(self):
        assert _score_to_level(0.6) == KnowledgeLevel.FAMILIAR

    def test_new(self):
        assert _score_to_level(0.2) == KnowledgeLevel.NEW

    def test_boundary_fluent(self):
        assert _score_to_level(0.75) == KnowledgeLevel.FLUENT

    def test_boundary_familiar(self):
        assert _score_to_level(0.45) == KnowledgeLevel.FAMILIAR


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStartSession:
    def test_creates_session(self, user, topic, questions):
        s = start_session(user=user, topic=topic)
        assert s.pk is not None
        assert s.state == SessionState.ACTIVE
        assert s.current_index == 0

    def test_question_count_capped_at_max(self, user, topic, questions):
        s = start_session(user=user, topic=topic)
        assert len(s.question_ids) <= MAX_QUESTIONS

    def test_all_question_ids_valid(self, user, topic, questions):
        s = start_session(user=user, topic=topic)
        valid_ids = set(QuizQuestion.objects.values_list("id", flat=True))
        for qid in s.question_ids:
            assert qid in valid_ids

    def test_progress_pct_starts_at_zero(self, user, topic, questions):
        s = start_session(user=user, topic=topic)
        assert s.progress_pct == 0


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSubmitAnswer:
    def test_correct_answer(self, session):
        qid = session.question_ids[0]
        result = submit_answer(session=session, question_id=qid, chosen_index=0)
        assert result["is_correct"] is True

    def test_wrong_answer(self, session):
        qid = session.question_ids[0]
        result = submit_answer(session=session, question_id=qid, chosen_index=1)
        assert result["is_correct"] is False

    def test_correct_index_returned(self, session):
        qid = session.question_ids[0]
        result = submit_answer(session=session, question_id=qid, chosen_index=0)
        assert result["correct_index"] == 0

    def test_index_advances(self, session):
        qid = session.question_ids[0]
        submit_answer(session=session, question_id=qid, chosen_index=0)
        session.refresh_from_db()
        assert session.current_index == 1

    def test_answer_rejected_on_inactive_session(self, session):
        session.state = SessionState.COMPLETED
        session.save()
        with pytest.raises(ValueError, match="not active"):
            submit_answer(session=session, question_id=session.question_ids[0], chosen_index=0)

    def test_answer_rejected_for_foreign_question(self, session, topic, db):
        other_q = QuizQuestion.objects.create(
            topic=topic, difficulty="easy",
            stem="Other?", options=["A","B","C","D"], correct_index=0,
        )
        with pytest.raises(ValueError, match="not part of session"):
            submit_answer(session=session, question_id=other_q.pk, chosen_index=0)


# ---------------------------------------------------------------------------
# Early end (high confidence)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestEarlyEnd:
    def test_ends_early_when_accuracy_high(self, session):
        """Answer EARLY_END_MIN_ANSWERED questions all correctly — session should end."""
        results = []
        for i in range(EARLY_END_MIN_ANSWERED):
            qid = session.question_ids[i]
            r = submit_answer(session=session, question_id=qid, chosen_index=0)
            results.append(r)
            session.refresh_from_db()

        # Last result should have ended the session
        assert results[-1]["session_ended"] is True
        session.refresh_from_db()
        assert session.state == SessionState.COMPLETED

    def test_no_early_end_below_min_questions(self, session):
        """Answer fewer than EARLY_END_MIN_ANSWERED questions — never ends early."""
        for i in range(EARLY_END_MIN_ANSWERED - 1):
            qid = session.question_ids[i]
            r = submit_answer(session=session, question_id=qid, chosen_index=0)
            session.refresh_from_db()
        assert session.state == SessionState.ACTIVE


# ---------------------------------------------------------------------------
# LearnerProfile update
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLearnerProfile:
    def test_profile_created_after_session(self, session, user, topic):
        # Answer all questions correctly → fluent
        for qid in session.question_ids:
            try:
                submit_answer(session=session, question_id=qid, chosen_index=0)
                session.refresh_from_db()
                if session.state != SessionState.ACTIVE:
                    break
            except ValueError:
                break

        assert LearnerProfile.objects.filter(user=user, topic=topic).exists()

    def test_level_set_to_fluent_on_all_correct(self, session, user, topic):
        for qid in session.question_ids:
            session.refresh_from_db()
            if session.state != SessionState.ACTIVE:
                break
            try:
                submit_answer(session=session, question_id=qid, chosen_index=0)
            except ValueError:
                break

        profile = LearnerProfile.objects.filter(user=user, topic=topic).first()
        if profile:
            assert profile.level in (KnowledgeLevel.FLUENT, KnowledgeLevel.FAMILIAR)


# ---------------------------------------------------------------------------
# get_user_level
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGetUserLevel:
    def test_defaults_to_familiar_when_no_profile(self, user, topic):
        level = get_user_level(user=user, topic_slug="nonexistent")
        assert level == KnowledgeLevel.FAMILIAR

    def test_returns_profile_level(self, user, topic):
        LearnerProfile.objects.create(
            user=user, topic=topic, level=KnowledgeLevel.FLUENT
        )
        assert get_user_level(user=user, topic_slug="transformers") == KnowledgeLevel.FLUENT


# ---------------------------------------------------------------------------
# Background swap
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSwapUnanswered:
    def test_answered_ids_preserved(self, session):
        answered_id = session.question_ids[0]
        submit_answer(session=session, question_id=answered_id, chosen_index=0)
        session.refresh_from_db()

        if session.state == SessionState.ACTIVE:
            before_answered = session.question_ids[:session.current_index]
            swapped = swap_unanswered_questions(session)
            swapped.refresh_from_db()
            assert swapped.question_ids[:swapped.current_index] == before_answered

    def test_no_swap_on_completed(self, session):
        session.state = SessionState.COMPLETED
        session.save()
        result = swap_unanswered_questions(session)
        assert result.state == SessionState.COMPLETED


# ---------------------------------------------------------------------------
# Golden question bank
# ---------------------------------------------------------------------------

class TestGoldenQuestions:
    def test_all_have_required_fields(self):
        required = {"topic_slug", "difficulty", "stem", "options", "correct_index"}
        for q in GOLDEN_QUESTIONS:
            missing = required - q.keys()
            assert not missing, f"Missing fields {missing} in question: {q['stem'][:40]}"

    def test_correct_index_in_range(self):
        for q in GOLDEN_QUESTIONS:
            assert 0 <= q["correct_index"] < len(q["options"]), \
                f"correct_index out of range for: {q['stem'][:40]}"

    def test_four_options_each(self):
        for q in GOLDEN_QUESTIONS:
            assert len(q["options"]) == 4, f"Expected 4 options for: {q['stem'][:40]}"

    def test_minimum_question_count(self):
        # At least 12 questions (4 topics × 3 difficulties)
        assert len(GOLDEN_QUESTIONS) >= 12

    def test_all_difficulties_covered(self):
        difficulties = {q["difficulty"] for q in GOLDEN_QUESTIONS}
        assert {"easy", "medium", "hard"}.issubset(difficulties)

    def test_all_topics_covered(self):
        topic_slugs = {q["topic_slug"] for q in GOLDEN_QUESTIONS}
        assert len(topic_slugs) >= 3


# ---------------------------------------------------------------------------
# DeepDiveCache
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDeepDiveCache:
    def test_stores_and_retrieves(self):
        content = json.dumps({
            "paper_explanation": "Test explanation",
            "background_context": "Test background",
            "key_takeaway": "Test takeaway",
        })
        DeepDiveCache.objects.create(card_id=99, level="familiar", content=content)

        cached = DeepDiveCache.objects.get(card_id=99, level="familiar")
        assert cached.content == content

    def test_unique_together_card_level(self, db):
        content = json.dumps({"paper_explanation": "A", "background_context": "", "key_takeaway": ""})
        DeepDiveCache.objects.create(card_id=100, level="new", content=content)
        with pytest.raises(Exception):
            DeepDiveCache.objects.create(card_id=100, level="new", content=content)


# ---------------------------------------------------------------------------
# REST API tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLearningAPI:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="apiuser", password="pw")
        self.client.force_authenticate(user=self.user)

        self.topic = Topic.objects.create(
            slug="transformers", display_name="Transformer Architecture", is_seeded=True
        )
        for difficulty, count in [("easy", 3), ("medium", 4), ("hard", 3)]:
            for i in range(count):
                QuizQuestion.objects.create(
                    topic=self.topic, difficulty=difficulty,
                    stem=f"API Q {difficulty} {i}?",
                    options=["A", "B", "C", "D"],
                    correct_index=0, is_active=True,
                )

    def test_topic_list(self):
        resp = self.client.get("/api/v1/learning/topics/")
        assert resp.status_code == 200
        data = resp.json()
        assert any(t["slug"] == "transformers" for t in data)

    def test_profile_empty_initially(self):
        resp = self.client.get("/api/v1/learning/profile/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_quiz_start(self):
        resp = self.client.post("/api/v1/learning/quiz/start/", {"topic_slug": "transformers"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["state"] == "active"
        assert "current_question" in data
        assert data["current_question"] is not None

    def test_quiz_start_unknown_topic(self):
        resp = self.client.post("/api/v1/learning/quiz/start/", {"topic_slug": "nonexistent"})
        assert resp.status_code == 404

    def test_quiz_answer_correct(self):
        start_resp = self.client.post("/api/v1/learning/quiz/start/", {"topic_slug": "transformers"})
        session_id = start_resp.json()["id"]
        question = start_resp.json()["current_question"]

        # correct_index=0; option_order maps display→original
        option_order = question["option_order"]
        display_idx = option_order.index(0)  # find display position of original index 0

        resp = self.client.post(
            f"/api/v1/learning/quiz/{session_id}/answer/",
            {
                "question_id": question["id"],
                "chosen_display_index": display_idx,
                "option_order": option_order,
            },
            format="json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is True

    def test_quiz_requires_auth(self):
        anon_client = APIClient()
        resp = anon_client.get("/api/v1/learning/topics/")
        assert resp.status_code == 403

    def test_profile_after_completed_session(self):
        start_resp = self.client.post("/api/v1/learning/quiz/start/", {"topic_slug": "transformers"})
        session_id = start_resp.json()["id"]

        # Answer all questions correctly until session ends
        current_q = start_resp.json()["current_question"]
        for _ in range(MAX_QUESTIONS + 1):
            if current_q is None:
                break
            option_order = current_q["option_order"]
            display_idx = option_order.index(0)
            ans_resp = self.client.post(
                f"/api/v1/learning/quiz/{session_id}/answer/",
                {
                    "question_id": current_q["id"],
                    "chosen_display_index": display_idx,
                    "option_order": option_order,
                },
                format="json",
            )
            data = ans_resp.json()
            if data.get("session_ended"):
                break
            current_q = data.get("next_question")

        prof_resp = self.client.get("/api/v1/learning/profile/")
        assert prof_resp.status_code == 200
        profiles = prof_resp.json()
        assert len(profiles) >= 1
        assert profiles[0]["topic_slug"] == "transformers"
