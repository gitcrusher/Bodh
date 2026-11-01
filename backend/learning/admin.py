"""
learning/admin.py — Django admin for the learning module (Step 2)
"""

from django.contrib import admin

from .models import DeepDiveCache, LearnerProfile, QuizAnswer, QuizQuestion, QuizSession, Topic


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["slug", "display_name", "is_seeded", "created_at"]
    list_filter = ["is_seeded"]
    search_fields = ["slug", "display_name"]


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ["id", "topic", "difficulty", "stem_short", "is_active", "logic_version"]
    list_filter = ["topic", "difficulty", "is_active"]
    search_fields = ["stem"]

    @admin.display(description="Stem (short)")
    def stem_short(self, obj: QuizQuestion) -> str:
        return obj.stem[:80]


@admin.register(LearnerProfile)
class LearnerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "topic", "level", "last_quiz_score", "streak_days", "calibrated_at"]
    list_filter = ["level", "topic"]
    search_fields = ["user__username", "topic__slug"]


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "topic", "state", "current_index", "final_score", "started_at"]
    list_filter = ["state", "topic"]
    search_fields = ["user__username"]


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "question", "chosen_index", "is_correct", "answered_at"]
    list_filter = ["is_correct"]


@admin.register(DeepDiveCache)
class DeepDiveCacheAdmin(admin.ModelAdmin):
    list_display = ["card_id", "level", "logic_version", "generated_at", "last_accessed_at"]
    list_filter = ["level"]
