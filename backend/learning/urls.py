"""
learning/urls.py — URL routes for /api/v1/learning/ (Step 2)
"""

from django.urls import path

from .views import (
    DeepDiveView,
    LearnerProfileView,
    QuizAnswerView,
    QuizSessionDetailView,
    QuizStartView,
    QuizSwapView,
    TopicListView,
)

app_name = "learning"

urlpatterns = [
    path("topics/", TopicListView.as_view(), name="topic-list"),
    path("profile/", LearnerProfileView.as_view(), name="learner-profile"),
    path("quiz/start/", QuizStartView.as_view(), name="quiz-start"),
    path("quiz/<int:session_id>/", QuizSessionDetailView.as_view(), name="quiz-detail"),
    path("quiz/<int:session_id>/answer/", QuizAnswerView.as_view(), name="quiz-answer"),
    path("quiz/<int:session_id>/swap/", QuizSwapView.as_view(), name="quiz-swap"),
    path("deep-dive/<int:card_id>/", DeepDiveView.as_view(), name="deep-dive"),
]
