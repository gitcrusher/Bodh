"""
learning/models.py — Step 2: Knowledge Calibration & Personalization

Tables owned by this module:
  - Topic              : seeded quiz topics (transformers, RAG, diffusion, …)
  - QuizQuestion       : question bank with options, answer, difficulty
  - LearnerProfile     : per-user per-topic level (new/familiar/fluent) + streak
  - QuizSession        : one quiz attempt (ordered question ids, state, scores)
  - QuizAnswer         : one answer within a session
  - DeepDiveCache      : cached level-adaptive deep-dive text per (card, level)

Rule 30: this module writes only its own tables.
Rule 40: trust tier, validity, and quiz scores are separate tables, never merged.
"""

from django.db import models
from django.contrib.auth.models import User


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class KnowledgeLevel(models.TextChoices):
    NEW = "new", "New"
    FAMILIAR = "familiar", "Familiar"
    FLUENT = "fluent", "Fluent"


class SessionState(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    ABANDONED = "abandoned", "Abandoned"


class Difficulty(models.TextChoices):
    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

class Topic(models.Model):
    """A calibratable knowledge domain (e.g. 'transformers', 'diffusion_models')."""

    slug = models.SlugField(max_length=80, unique=True)
    display_name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    # Whether this topic appears in the onboarding quiz batch
    is_seeded = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_name"]

    def __str__(self) -> str:
        return self.display_name


# ---------------------------------------------------------------------------
# Question bank
# ---------------------------------------------------------------------------

class QuizQuestion(models.Model):
    """A multiple-choice question tied to a topic and difficulty level.

    Rule 41: question bank must be reviewed before the quiz critic ships.
    design.md §7: option order is randomised per attempt (done in the view).
    """

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="questions")
    difficulty = models.CharField(
        max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM
    )
    # The question stem
    stem = models.TextField()
    # JSON list of option strings (4 options)
    options = models.JSONField()
    # Index into options (0-based) of the correct answer
    correct_index = models.PositiveSmallIntegerField()
    # Short explanation shown after the answer is submitted
    explanation = models.TextField(blank=True)
    # logic_version so eval re-runs when question changes (Rule 7)
    logic_version = models.CharField(max_length=20, default="1.0")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["topic", "difficulty"]

    def __str__(self) -> str:
        return f"[{self.topic.slug}/{self.difficulty}] {self.stem[:60]}"


# ---------------------------------------------------------------------------
# Learner profile
# ---------------------------------------------------------------------------

class LearnerProfile(models.Model):
    """Per-user per-topic calibrated knowledge level.

    A retake resets behavioral_adjustment (Rule 10.77 analogue) but not the
    quiz score; the quiz score is the authoritative level.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="learner_profiles")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="learner_profiles")

    level = models.CharField(
        max_length=10, choices=KnowledgeLevel.choices, default=KnowledgeLevel.FAMILIAR
    )
    # Raw score from last completed quiz (0.0–1.0)
    last_quiz_score = models.FloatField(null=True, blank=True)
    # Number of questions answered correctly across all sessions
    correct_count = models.PositiveIntegerField(default=0)
    total_count = models.PositiveIntegerField(default=0)
    # Streak: consecutive days with at least one correct answer
    streak_days = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    calibrated_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "topic")]
        ordering = ["topic__display_name"]

    def __str__(self) -> str:
        return f"{self.user.username} · {self.topic.slug} · {self.level}"

    @property
    def accuracy(self) -> float | None:
        if self.total_count == 0:
            return None
        return self.correct_count / self.total_count


# ---------------------------------------------------------------------------
# Quiz session
# ---------------------------------------------------------------------------

class QuizSession(models.Model):
    """One quiz attempt by a user for one topic.

    design.md §7:
    - Up to 10 questions; ends early when confidence is high.
    - No back button (strictly one-way).
    - Backgrounded beyond a few seconds → unanswered questions swapped.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_sessions")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="quiz_sessions")
    state = models.CharField(
        max_length=12, choices=SessionState.choices, default=SessionState.ACTIVE
    )
    # Ordered list of QuizQuestion PKs selected for this session
    question_ids = models.JSONField(default=list)
    # Current position in question_ids (0-based)
    current_index = models.PositiveSmallIntegerField(default=0)
    # Score at session end (0.0–1.0)
    final_score = models.FloatField(null=True, blank=True)
    # Computed level assigned at end
    assigned_level = models.CharField(
        max_length=10, choices=KnowledgeLevel.choices, null=True, blank=True
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"Session#{self.pk} {self.user.username}·{self.topic.slug} [{self.state}]"

    @property
    def is_complete(self) -> bool:
        return self.state == SessionState.COMPLETED

    @property
    def progress_pct(self) -> int:
        total = len(self.question_ids)
        if total == 0:
            return 0
        return min(100, int(self.current_index / total * 100))


# ---------------------------------------------------------------------------
# Quiz answer
# ---------------------------------------------------------------------------

class QuizAnswer(models.Model):
    """One submitted answer within a QuizSession.

    Strictly append-only: once submitted, answers are never edited (Rule §7 design.md).
    """

    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(QuizQuestion, on_delete=models.PROTECT, related_name="answers")
    # The index the user chose
    chosen_index = models.PositiveSmallIntegerField()
    is_correct = models.BooleanField()
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Each question can only be answered once per session
        unique_together = [("session", "question")]
        ordering = ["answered_at"]

    def __str__(self) -> str:
        mark = "✓" if self.is_correct else "✗"
        return f"{mark} Session#{self.session_id} Q#{self.question_id}"


# ---------------------------------------------------------------------------
# Level-adaptive deep-dive cache
# ---------------------------------------------------------------------------

class DeepDiveCache(models.Model):
    """Cached level-adaptive deep-dive text for a card at a specific level.

    Rule 20: generated lazily on first open, then cached.
    Rule 20 also: never pre-generate all three levels.
    """

    # Card is referenced by ID from the research module (no cross-module FK —
    # Rule 29: no cross-module internal imports; use integer reference instead)
    card_id = models.IntegerField(db_index=True)
    level = models.CharField(max_length=10, choices=KnowledgeLevel.choices)
    # The generated deep-dive text
    content = models.TextField()
    # Which logic_version produced this (Rule 7)
    logic_version = models.CharField(max_length=20, default="1.0")
    generated_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("card_id", "level")]
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"DeepDive card#{self.card_id} [{self.level}]"
