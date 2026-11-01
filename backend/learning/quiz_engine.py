"""
learning/quiz_engine.py — Quiz session logic (Step 2)

Responsibilities:
  - Select questions for a session (difficulty-ladder selection)
  - Score an answer and decide whether to end early (high confidence)
  - Compute final level from score
  - Swap unanswered questions when session is backgrounded (design.md §7)

No LLM calls here — this is pure Python. The quiz_critic (LangGraph node)
calls into this engine after generation.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from django.contrib.auth.models import User

from .models import (
    Difficulty,
    KnowledgeLevel,
    LearnerProfile,
    QuizAnswer,
    QuizQuestion,
    QuizSession,
    SessionState,
    Topic,
)

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_QUESTIONS = 10
# End session early if running accuracy >= this threshold after min questions
EARLY_END_ACCURACY = 0.85
EARLY_END_MIN_ANSWERED = 4

# Score → level thresholds (inclusive lower bound)
LEVEL_THRESHOLDS = [
    (0.75, KnowledgeLevel.FLUENT),
    (0.45, KnowledgeLevel.FAMILIAR),
    (0.0, KnowledgeLevel.NEW),
]

# Question count per difficulty tier to pick from
DIFFICULTY_DISTRIBUTION = {
    Difficulty.EASY: 3,
    Difficulty.MEDIUM: 4,
    Difficulty.HARD: 3,
}


# ---------------------------------------------------------------------------
# Session creation
# ---------------------------------------------------------------------------

def start_session(user: User, topic: Topic) -> QuizSession:
    """Create a new QuizSession for (user, topic).

    Selects up to MAX_QUESTIONS questions using the difficulty distribution.
    Option order is randomised in the view layer, not here (design.md §7).
    """
    question_ids = _select_question_ids(topic)

    session = QuizSession.objects.create(
        user=user,
        topic=topic,
        state=SessionState.ACTIVE,
        question_ids=question_ids,
        current_index=0,
    )
    return session


def _select_question_ids(topic: Topic) -> list[int]:
    """Pick questions from the bank using the difficulty distribution."""
    ids: list[int] = []
    for difficulty, count in DIFFICULTY_DISTRIBUTION.items():
        qs = list(
            QuizQuestion.objects.filter(
                topic=topic, difficulty=difficulty, is_active=True
            ).values_list("id", flat=True)
        )
        random.shuffle(qs)
        ids.extend(qs[:count])

    random.shuffle(ids)
    return ids[:MAX_QUESTIONS]


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------

def submit_answer(session: QuizSession, question_id: int, chosen_index: int) -> dict:
    """Record one answer and return result dict.

    Returns:
        {
            "is_correct": bool,
            "correct_index": int,
            "explanation": str,
            "session_ended": bool,   # True if session finished early or normally
            "next_question_id": int | None,
        }

    Raises:
        ValueError if session is not active or question not in session.
    """
    if session.state != SessionState.ACTIVE:
        raise ValueError(f"Session #{session.pk} is not active (state={session.state})")

    if question_id not in session.question_ids:
        raise ValueError(f"Question #{question_id} is not part of session #{session.pk}")

    question = QuizQuestion.objects.get(pk=question_id)
    is_correct = chosen_index == question.correct_index

    QuizAnswer.objects.create(
        session=session,
        question=question,
        chosen_index=chosen_index,
        is_correct=is_correct,
    )

    # Advance index
    session.current_index += 1
    session.save(update_fields=["current_index"])

    # Check early-end or normal end
    answered = session.answers.count()
    correct = session.answers.filter(is_correct=True).count()
    accuracy = correct / answered if answered > 0 else 0.0

    session_ended = False
    next_question_id = None

    end_early = (
        answered >= EARLY_END_MIN_ANSWERED and accuracy >= EARLY_END_ACCURACY
    )
    all_done = session.current_index >= len(session.question_ids)

    if end_early or all_done:
        session_ended = True
        _finalize_session(session, correct, answered)
    else:
        # Next question ID
        next_idx = session.current_index
        if next_idx < len(session.question_ids):
            next_question_id = session.question_ids[next_idx]

    return {
        "is_correct": is_correct,
        "correct_index": question.correct_index,
        "explanation": question.explanation,
        "session_ended": session_ended,
        "next_question_id": next_question_id,
        "current_accuracy": round(accuracy, 3),
    }


# ---------------------------------------------------------------------------
# Session finalization
# ---------------------------------------------------------------------------

def _finalize_session(session: QuizSession, correct: int, total: int) -> None:
    """Mark session completed and update the LearnerProfile."""
    score = correct / total if total > 0 else 0.0
    level = _score_to_level(score)

    session.state = SessionState.COMPLETED
    session.final_score = score
    session.assigned_level = level
    session.completed_at = datetime.now(tz=timezone.utc)
    session.save(update_fields=["state", "final_score", "assigned_level", "completed_at"])

    _update_profile(session.user, session.topic, score, level, correct, total)


def _score_to_level(score: float) -> str:
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return KnowledgeLevel.NEW


def _update_profile(
    user: User,
    topic: Topic,
    score: float,
    level: str,
    correct: int,
    total: int,
) -> None:
    """Upsert LearnerProfile with new quiz result."""
    from datetime import date

    today = date.today()
    profile, _ = LearnerProfile.objects.get_or_create(user=user, topic=topic)

    # Update streak
    if profile.last_activity_date == today:
        pass  # same day, no increment
    elif profile.last_activity_date and (today - profile.last_activity_date).days == 1:
        profile.streak_days += 1
    else:
        profile.streak_days = 1

    profile.level = level
    profile.last_quiz_score = score
    profile.correct_count += correct
    profile.total_count += total
    profile.last_activity_date = today
    profile.calibrated_at = datetime.now(tz=timezone.utc)
    profile.save()


# ---------------------------------------------------------------------------
# Background swap (design.md §7)
# ---------------------------------------------------------------------------

def swap_unanswered_questions(session: QuizSession) -> QuizSession:
    """Replace remaining unanswered question IDs with fresh ones.

    Called when the app detects the session was backgrounded beyond a few
    seconds. Answered questions (up to current_index) are preserved.
    """
    if session.state != SessionState.ACTIVE:
        return session

    answered_ids = list(session.question_ids[: session.current_index])
    remaining_count = len(session.question_ids) - session.current_index

    # Pick fresh questions excluding already-answered ones
    fresh = list(
        QuizQuestion.objects.filter(topic=session.topic, is_active=True)
        .exclude(pk__in=answered_ids)
        .exclude(pk__in=session.question_ids[session.current_index:])
        .values_list("id", flat=True)
    )
    random.shuffle(fresh)
    new_ids = answered_ids + fresh[:remaining_count]

    session.question_ids = new_ids
    session.save(update_fields=["question_ids"])
    return session


# ---------------------------------------------------------------------------
# Level lookup (used by deep-dive generator)
# ---------------------------------------------------------------------------

def get_user_level(user: User, topic_slug: str) -> str:
    """Return the user's calibrated level for a topic, defaulting to 'familiar'."""
    try:
        profile = LearnerProfile.objects.get(user=user, topic__slug=topic_slug)
        return profile.level
    except LearnerProfile.DoesNotExist:
        return KnowledgeLevel.FAMILIAR
