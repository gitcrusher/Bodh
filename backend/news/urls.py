"""
news/urls.py

URL patterns for the AI News Ingestion Engine.
"""

from django.urls import path
from news.views import (
    NewsArticleDetailView,
    NewsArticleListView,
    NewsArticlePromoteView,
    NewsFetchTriggerView,
    NewsSeedSourcesView,
    NewsSourceListView,
)

urlpatterns = [
    path("articles/", NewsArticleListView.as_view(), name="news_article_list"),
    path("articles/<int:pk>/", NewsArticleDetailView.as_view(), name="news_article_detail"),
    path("articles/<int:pk>/promote/", NewsArticlePromoteView.as_view(), name="news_article_promote"),
    path("sources/", NewsSourceListView.as_view(), name="news_source_list"),
    path("fetch/", NewsFetchTriggerView.as_view(), name="news_fetch_trigger"),
    path("seed/", NewsSeedSourcesView.as_view(), name="news_seed_sources"),
]

