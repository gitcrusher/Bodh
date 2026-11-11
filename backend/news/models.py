"""
news/models.py

Models for the Multi-Source AI News Engine:
  - NewsSource: Stores metadata and ingestion endpoints for AI labs, newsletters,
    YouTube channels, company blogs, and community digests.
  - NewsArticle: Standardized storage for fetched news articles, preserving raw content,
    tags, entity mentions, and optional synthesis into 60-second research cards.
"""

from django.db import models
from django.utils import timezone


CATEGORY_CHOICES = [
    ("ai_lab", "AI Research Lab"),
    ("company", "Company / Industry"),
    ("newsletter", "Technical Newsletter / Blog"),
    ("youtube", "YouTube Channel"),
    ("podcast", "Technical Podcast"),
    ("eval_benchmark", "Evaluation & Benchmark"),
    ("community", "Community Digest / Forum"),
]

SOURCE_TYPE_CHOICES = [
    ("primary", "Primary Source (Lab/Author)"),
    ("independent_analysis", "Independent Analysis"),
    ("vendor_marketing", "Vendor Marketing (Rule 50: Self-Report)"),
    ("community", "Community Aggregation"),
    ("news_media", "News & Media"),
    ("academic", "Academic / Preprint"),
]


class NewsSource(models.Model):
    """
    Catalog of verified news endpoints (RSS, Atom, APIs, YouTube channels).
    """

    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True)
    category = models.CharField(
        max_length=50, choices=CATEGORY_CHOICES, default="company"
    )
    source_type = models.CharField(
        max_length=50, choices=SOURCE_TYPE_CHOICES, default="primary"
    )
    feed_url = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="Direct RSS/Atom feed or API endpoint",
    )
    website_url = models.URLField(max_length=1000, blank=True, null=True)
    is_active = models.BooleanField(
        default=True, help_text="Whether this source is currently polled/fetched"
    )
    is_verified = models.BooleanField(
        default=True, help_text="Whether endpoint schema has been validated"
    )
    update_frequency = models.CharField(
        max_length=50, default="daily", help_text="hourly, daily, weekly, per_event"
    )
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    fetch_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]
        verbose_name = "News Source"
        verbose_name_plural = "News Sources"

    def __str__(self) -> str:
        return f"{self.name} [{self.category}]"


class NewsArticle(models.Model):
    """
    Standardized news article fetched across any medium.
    """

    source = models.ForeignKey(
        NewsSource,
        on_delete=models.CASCADE,
        related_name="articles",
        null=True,
        blank=True,
    )
    external_id = models.CharField(
        max_length=512,
        help_text="Canonical URL hash, guid, or provider ID for deduplication",
    )
    title = models.CharField(max_length=512)
    url = models.URLField(max_length=1000)
    author = models.CharField(max_length=255, blank=True, default="")
    published_at = models.DateTimeField(default=timezone.now)
    summary = models.TextField(
        blank=True, default="", help_text="Short abstract or initial summary"
    )
    content = models.TextField(
        blank=True, default="", help_text="Full text or transcript snippet if available"
    )
    category = models.CharField(max_length=50, default="company")
    tags = models.JSONField(
        default=list, blank=True, help_text="List of topic tags e.g. ['llm', 'agents']"
    )
    candidate_entities = models.JSONField(
        default=list,
        blank=True,
        help_text="Detected companies, models, or repos (e.g. ['OpenAI', 'GPT-4o'])",
    )
    candidate_techniques = models.JSONField(
        default=list,
        blank=True,
        help_text="Detected algorithmic techniques or benchmarks",
    )
    is_developer_self_report = models.BooleanField(
        default=False,
        help_text="Rule 50: True if published directly by vendor without independent benchmark",
    )
    is_processed_to_card = models.BooleanField(
        default=False,
        help_text="True if this article was synthesized into a research Card",
    )
    card_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Optional ID of corresponding Card in research app",
    )
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-published_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["url"], name="unique_news_article_url"
            ),
        ]
        verbose_name = "News Article"
        verbose_name_plural = "News Articles"

    def __str__(self) -> str:
        return f"{self.title[:80]} ({self.published_at.strftime('%Y-%m-%d')})"

