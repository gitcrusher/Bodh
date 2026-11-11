"""
news/serializers.py

DRF Serializers for NewsSource and NewsArticle.
"""

from rest_framework import serializers
from news.models import NewsArticle, NewsSource


class NewsSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NewsSource
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "source_type",
            "feed_url",
            "website_url",
            "is_active",
            "is_verified",
            "update_frequency",
            "last_fetched_at",
            "fetch_count",
            "error_count",
        ]


class NewsArticleSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True)
    source_category = serializers.CharField(source="source.category", read_only=True)

    class Meta:
        model = NewsArticle
        fields = [
            "id",
            "source_name",
            "source_category",
            "external_id",
            "title",
            "url",
            "author",
            "published_at",
            "summary",
            "content",
            "category",
            "tags",
            "candidate_entities",
            "candidate_techniques",
            "is_developer_self_report",
            "is_processed_to_card",
            "card_id",
            "fetched_at",
        ]

