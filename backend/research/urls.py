"""research/urls.py — URL patterns for the research module."""

from django.urls import path

from research.views import (
    CardDetailView,
    CardFeedView,
    CardReportView,
    DynamicPaperLinksView,
    PaperChatHistoryView,
    PaperChatView,
    RelatedCardsView,
    SourceListView,
)

app_name = "research"

urlpatterns = [
    path("cards/", CardFeedView.as_view(), name="card-feed"),
    path("cards/<int:card_id>/", CardDetailView.as_view(), name="card-detail"),
    path("cards/<int:card_id>/report/", CardReportView.as_view(), name="card-report"),
    path("cards/<int:card_id>/chat/", PaperChatView.as_view(), name="card-chat"),
    path(
        "cards/<int:card_id>/chat/<int:session_id>/",
        PaperChatHistoryView.as_view(),
        name="card-chat-history",
    ),
    path("cards/<int:card_id>/related/", RelatedCardsView.as_view(), name="card-related"),
    path("cards/<int:card_id>/links/", DynamicPaperLinksView.as_view(), name="card-links"),
    path("sources/", SourceListView.as_view(), name="source-list"),
]
