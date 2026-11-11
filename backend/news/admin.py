"""
news/admin.py

Django admin configuration for NewsSource and NewsArticle.
"""

from django.contrib import admin
from news.models import NewsArticle, NewsSource


@admin.register(NewsSource)
class NewsSourceAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "source_type", "is_active", "fetch_count", "last_fetched_at"]
    list_filter = ["category", "source_type", "is_active", "is_verified"]
    search_fields = ["name", "slug", "feed_url", "website_url"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "source",
        "published_at",
        "is_developer_self_report",
        "is_processed_to_card",
    ]
    list_filter = ["category", "is_developer_self_report", "is_processed_to_card", "published_at"]
    search_fields = ["title", "summary", "content", "tags", "candidate_entities"]
    readonly_fields = ["fetched_at"]

