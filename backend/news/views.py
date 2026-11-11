"""
news/views.py

API Views for the AI News Ingestion Engine:
  - GET  /api/v1/news/articles/        — List recent AI news articles
  - GET  /api/v1/news/articles/<id>/   — Retrieve single article details
  - GET  /api/v1/news/sources/         — List news sources and health status
  - POST /api/v1/news/fetch/           — Trigger on-demand news fetch
  - POST /api/v1/news/seed/            — Seed curated sources (labs, YouTube, newsletters)
  - POST /api/v1/news/articles/<id>/promote/ — Promote article into research Card
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from news.models import NewsArticle, NewsSource
from news.serializers import NewsArticleSerializer, NewsSourceSerializer
from news.services.news_service import NewsService


class NewsArticleListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        category = request.query_params.get("category")
        entity = request.query_params.get("entity")
        search = request.query_params.get("search")
        limit = min(int(request.query_params.get("limit", 30)), 100)

        qs = NewsArticle.objects.select_related("source").all()

        if category:
            qs = qs.filter(category=category)
        if search:
            qs = qs.filter(title__icontains=search)
        if entity:
            qs = qs.filter(candidate_entities__contains=[entity])

        articles = qs[:limit]
        serializer = NewsArticleSerializer(articles, many=True)
        return Response(
            {
                "count": len(articles),
                "total": qs.count(),
                "results": serializer.data,
            }
        )


class NewsArticleDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: int) -> Response:
        try:
            article = NewsArticle.objects.select_related("source").get(pk=pk)
        except NewsArticle.DoesNotExist:
            return Response(
                {"error": f"NewsArticle with ID {pk} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = NewsArticleSerializer(article)
        return Response(serializer.data)


class NewsSourceListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        sources = NewsSource.objects.all()
        serializer = NewsSourceSerializer(sources, many=True)
        return Response(
            {
                "count": sources.count(),
                "active_count": sources.filter(is_active=True).count(),
                "results": serializer.data,
            }
        )


class NewsFetchTriggerView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        source_slug = request.data.get("source_slug")
        query = request.data.get("query")
        limit = int(request.data.get("limit", 5))

        if query:
            # Tavily breaking news search
            articles = NewsService.fetch_breaking_tavily(query=query, limit=limit)
            return Response(
                {
                    "mode": "tavily_search",
                    "query": query,
                    "fetched_count": len(articles),
                    "articles": NewsArticleSerializer(articles, many=True).data,
                }
            )

        if source_slug:
            source = NewsSource.objects.filter(slug=source_slug).first()
            if not source:
                return Response(
                    {"error": f"Source with slug '{source_slug}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            articles = NewsService.fetch_from_source(source, limit=limit)
            return Response(
                {
                    "source": source.name,
                    "fetched_count": len(articles),
                    "articles": NewsArticleSerializer(articles, many=True).data,
                }
            )

        # Poll all active sources
        summary = NewsService.fetch_all_active(limit_per_source=limit)
        return Response(
            {
                "mode": "all_active_sources",
                "total_sources_polled": len(summary),
                "summary": summary,
            }
        )


class NewsSeedSourcesView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        created_count = NewsService.seed_default_sources()
        total_count = NewsSource.objects.count()
        return Response(
            {
                "message": f"Successfully seeded {created_count} new news sources.",
                "created": created_count,
                "total_sources": total_count,
            }
        )


class NewsArticlePromoteView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, pk: int) -> Response:
        card_id = NewsService.promote_to_research_card(pk)
        if not card_id:
            return Response(
                {"error": f"Could not promote article {pk} into a Card."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": f"Successfully synthesized article {pk} into research Card {card_id}.",
                "article_id": pk,
                "card_id": card_id,
            }
        )

