"""
learning/serializers.py — DRF serializers for the learning module (Step 2)
"""

import random

from rest_framework import serializers

from .models import (
    DeepDiveCache,
    KnowledgeLevel,
    LearnerProfile,
    QuizAnswer,
    QuizQuestion,
    QuizSession,
    Topic,
)


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------

class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ["id", "slug", "display_name", "description", "is_seeded"]


# ---------------------------------------------------------------------------
# Question (with randomised option order — design.md §7)
# ---------------------------------------------------------------------------

class QuizQuestionSerializer(serializers.ModelSerializer):
    """Returns the question with options in a randomised order.

    The mapping from display position → original index is included so the
    client can POST back the chosen display index and the view can convert it.
    """

    options_randomised = serializers.SerializerMethodField()
    # Maps display index → original option index
    option_order = serializers.SerializerMethodField()

    class Meta:
        model = QuizQuestion
        fields = [
            "id", "topic", "difficulty", "stem",
            "options_randomised", "option_order",
        ]

    def _get_order(self, obj: QuizQuestion) -> list[int]:
        # Cache per-request so both methods use the same shuffle
        cache_key = f"_order_{obj.pk}"
        if not hasattr(self, cache_key):
            order = list(range(len(obj.options)))
            random.shuffle(order)
            setattr(self, cache_key, order)
        return getattr(self, cache_key)

    def get_options_randomised(self, obj: QuizQuestion) -> list[str]:
        order = self._get_order(obj)
        return [obj.options[i] for i in order]

    def get_option_order(self, obj: QuizQuestion) -> list[int]:
        return self._get_order(obj)


# ---------------------------------------------------------------------------
# Learner profile
# ---------------------------------------------------------------------------

class LearnerProfileSerializer(serializers.ModelSerializer):
    topic_slug = serializers.CharField(source="topic.slug", read_only=True)
    topic_name = serializers.CharField(source="topic.display_name", read_only=True)
    accuracy = serializers.FloatField(read_only=True)

    class Meta:
        model = LearnerProfile
        fields = [
            "id", "topic_slug", "topic_name", "level",
            "last_quiz_score", "accuracy",
            "correct_count", "total_count",
            "streak_days", "calibrated_at", "updated_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Quiz session
# ---------------------------------------------------------------------------

class QuizSessionSerializer(serializers.ModelSerializer):
    topic_slug = serializers.CharField(source="topic.slug", read_only=True)
    topic_name = serializers.CharField(source="topic.display_name", read_only=True)
    progress_pct = serializers.IntegerField(read_only=True)
    total_questions = serializers.SerializerMethodField()

    class Meta:
        model = QuizSession
        fields = [
            "id", "topic_slug", "topic_name", "state",
            "current_index", "total_questions", "progress_pct",
            "final_score", "assigned_level",
            "started_at", "completed_at",
        ]
        read_only_fields = fields

    def get_total_questions(self, obj: QuizSession) -> int:
        return len(obj.question_ids)


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------

class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    # The display index (from options_randomised) the user chose
    chosen_display_index = serializers.IntegerField(min_value=0, max_value=3)
    # The original option_order from the question response (client echoes it back)
    option_order = serializers.ListField(child=serializers.IntegerField(), min_length=2)

    def validate(self, data: dict) -> dict:
        order = data["option_order"]
        idx = data["chosen_display_index"]
        if idx >= len(order):
            raise serializers.ValidationError("chosen_display_index out of range for option_order.")
        # Convert display index → original index
        data["chosen_original_index"] = order[idx]
        return data


# ---------------------------------------------------------------------------
# Deep-dive response
# ---------------------------------------------------------------------------

class DeepDiveResponseSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=KnowledgeLevel.choices)
    paper_explanation = serializers.CharField()
    background_context = serializers.CharField()
    key_takeaway = serializers.CharField()
    from_cache = serializers.BooleanField()
