"""
research/models.py

Data model for the research module (Step 1).

Tables defined here:
  sources               - registered ingestion sources (arXiv, etc.)
  raw_items             - one row per fetched paper (identity + transient content)
  cards                 - one row per published 60-second card
  card_sources          - additional outlets covering the same underlying paper
  paper_validity_signals - per-paper venue + affiliation data from Semantic Scholar
  content_reports       - reader-submitted issue reports

Design notes (from system design §6):
- raw_items.raw_content is transient: nulled after grace_period_expires_at.
- raw_items.embedding drives near-duplicate detection (cosine > 0.92).
- cards.embedding (headline + summary) powers Research Assistant coarse retrieval.
- paper_chat_chunks lives in Step 3; not created here.
- JSONField used for array-like columns so SQLite tests work without Postgres.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from research.fields import VectorField


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class Source(models.Model):
    """
    A registered ingestion source. One row per origin (e.g. "arXiv cs.AI").

    `rate_limit_policy` is a JSON blob read by the central RateLimiter in
    core.fetcher.rate_limiter.  Example::

        {"calls_per_second": 0.33, "burst": 1}

    `daily_request_cap` limits how many HTTP requests the fetcher may make in
    a single daily run for this source.
    """

    FETCH_METHOD_CHOICES = [("api", "API"), ("scraper", "Scraper")]
    TRUST_TIER_CHOICES = [
        (1, "Tier 1 — Primary"),
        (2, "Tier 2 — Verified Press/Analyst"),
        (3, "Tier 3 — Aggregator/Community"),
    ]
    PUBLISHER_REL_CHOICES = [
        ("independent", "Independent"),
        ("developer_self_report", "Developer Self-Report"),
    ]

    name = models.CharField(max_length=200)
    url = models.URLField(max_length=2000)
    fetch_interval_min = models.IntegerField(default=1440)  # 1 day
    active = models.BooleanField(default=True)
    # List of knowledge-type tags, e.g. ["research", "new_model"]
    knowledge_type = models.JSONField(default=list)
    trust_tier = models.IntegerField(choices=TRUST_TIER_CHOICES, default=1)
    fetch_method = models.CharField(
        max_length=20, choices=FETCH_METHOD_CHOICES, default="api"
    )
    last_successful_run_at = models.DateTimeField(null=True, blank=True)
    publisher_relationship = models.CharField(
        max_length=30, choices=PUBLISHER_REL_CHOICES, default="independent"
    )
    rate_limit_policy = models.JSONField(default=dict)
    daily_request_cap = models.IntegerField(default=1000)

    class Meta:
        db_table = "sources"

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Raw items
# ---------------------------------------------------------------------------


class RawItem(models.Model):
    """
    One row per paper fetched from a source.

    Identity fields (external_id, content_hash, url, published_at) are tiny
    and permanent — they are the gate for "never re-fetch/never reprocess."
    raw_content is transient: nulled after grace_period_expires_at (7–14 days).
    embedding is kept for 90 days (near-dup detection window) then cleared.

    Unique index on (source, external_id) is the cheapest possible dedup gate:
    one indexed lookup before any LLM call.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("processed", "Processed"),
        ("duplicate", "Duplicate"),
        ("discarded", "Discarded"),
    ]

    source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="raw_items"
    )
    external_id = models.CharField(max_length=500)
    title = models.TextField()
    url = models.URLField(max_length=2000)
    published_at = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64, null=True, blank=True)
    embedding = VectorField(dimensions=384, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    # Transient — cleared after grace_period_expires_at
    raw_content = models.TextField(null=True, blank=True)
    grace_period_expires_at = models.DateTimeField(null=True, blank=True)
    figure_url = models.URLField(max_length=2000, null=True, blank=True)

    class Meta:
        db_table = "raw_items"
        unique_together = [("source", "external_id")]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["published_at"]),
        ]

    def __str__(self):
        return f"[{self.source.name}] {self.title[:60]}"


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------


class Card(models.Model):
    """
    The published 60-second card — the distilled output of the pipeline.

    deep_dive_base:
      Generated at ingest for priority cards only (Tier 1, canon candidates,
      trending-technique matches). For all others it is NULL and generated on
      first open, then cached. Never pre-generate all three levels up front.

    needs_review:
      Set True when the number/entity check failed and we fell back to the
      extractive summary. Shown in the UI and the admin review queue.

    embedding (headline + summary): powers Research Assistant coarse retrieval.
    """

    CATEGORY_CHOICES = [
        ("research", "Research"),
        ("new_model", "New Model"),
        ("threat", "Threat/Safety"),
        ("opinion", "Opinion/Analysis"),
    ]

    raw_item = models.OneToOneField(
        RawItem, on_delete=models.PROTECT, related_name="card"
    )
    category = models.CharField(
        max_length=30, choices=CATEGORY_CHOICES, default="research"
    )
    headline = models.TextField()
    summary_60s = models.TextField()  # 3–4 bullets, ~150 words
    tags = models.JSONField(default=list)
    candidate_techniques = models.JSONField(default=list)  # from summarizer, reused by technique-grounding critic
    # Nullable — generated on demand for non-priority cards
    deep_dive_base = models.TextField(null=True, blank=True)
    # headline + summary embedding — powers coarse retrieval
    embedding = VectorField(dimensions=384, null=True, blank=True)
    source_url = models.URLField(max_length=2000)
    image_url = models.URLField(max_length=2000, null=True, blank=True)
    published_at = models.DateTimeField()
    # True = number/entity check failed → extractive fallback used
    needs_review = models.BooleanField(default=False)
    # Rule 58: True if fresh breakthrough for primary vertical feed; False if foundational prior-art in related clusters
    is_primary_feed = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cards"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["category"]),
            models.Index(fields=["-published_at"]),
        ]

    def __str__(self):
        return self.headline[:80]


# ---------------------------------------------------------------------------
# Card sources (additional outlets covering the same paper)
# ---------------------------------------------------------------------------


class CardSource(models.Model):
    """
    When a second (or third) outlet covers a paper already summarised,
    dedup writes here instead of creating a duplicate card.
    One card → multiple source attributions.
    """

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="card_sources")
    source_url = models.URLField(max_length=2000)
    source = models.ForeignKey(
        Source, on_delete=models.PROTECT, null=True, blank=True
    )
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "card_sources"

    def __str__(self):
        return f"CardSource for card_id={self.card_id}"


# ---------------------------------------------------------------------------
# Per-paper validity signals (Semantic Scholar)
# ---------------------------------------------------------------------------


class PaperValiditySignal(models.Model):
    """
    Venue tier + affiliation tier per paper — a separate axis from source
    trust tier (§7 system design).

    data_source: which external API provided this data.
    venue_tier / affiliation_tier: 1 = strongest signal, 3 = weakest / unknown.
    Shown as a badge on the card; never used to suppress a paper from the feed.
    """

    DATA_SOURCE_CHOICES = [
        ("semantic_scholar", "Semantic Scholar"),
        ("arxiv_metadata", "arXiv Metadata"),
    ]

    card = models.OneToOneField(
        Card, on_delete=models.CASCADE, related_name="validity_signal"
    )
    venue = models.CharField(max_length=500, blank=True, default="")
    venue_tier = models.IntegerField(default=3)  # 1=top, 2=peer-reviewed, 3=preprint/unknown
    authors = models.JSONField(default=list)  # [{name, affiliations}]
    affiliation_tier = models.IntegerField(default=3)  # 1=top lab/uni, 2=known, 3=unknown
    data_source = models.CharField(
        max_length=30, choices=DATA_SOURCE_CHOICES, default="arxiv_metadata"
    )
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "paper_validity_signals"

    def __str__(self):
        return f"Validity for card_id={self.card_id}: venue={self.venue or 'none'}"


# ---------------------------------------------------------------------------
# Content reports
# ---------------------------------------------------------------------------


class ContentReport(models.Model):
    """
    Reader-submitted issue reports — written to via POST /api/v1/cards/{id}/report.
    Reviewed in the Django admin; resolved flag cleared by an admin.
    """

    REASON_CHOICES = [
        ("factual_error", "Factual Error"),
        ("wrong_summary", "Incorrect Summary"),
        ("broken_link", "Broken Source Link"),
        ("other", "Other"),
    ]

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=30, choices=REASON_CHOICES)
    detail = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        db_table = "content_reports"

    def __str__(self):
        return f"Report({self.reason}) on card_id={self.card_id}"


# ---------------------------------------------------------------------------
# Step 3: Paper chat chunks, sessions, and messages
# ---------------------------------------------------------------------------


class PaperChatChunk(models.Model):
    """
    Chunks of paper full text generated on demand on first chat open.
    Rule 46: Never store raw PDF; fetch, extract text, chunk, discard binary.
    Rule 47: Check if chunks already exist for card_id; if so reuse and touch last_accessed_at.
    Rule 38: Evicted after 30 days unused by retention runner.
    """

    card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name="chat_chunks"
    )
    chunk_index = models.PositiveIntegerField()
    chunk_text = models.TextField()
    embedding = VectorField(dimensions=384, null=True, blank=True)
    embedding_model_version = models.CharField(
        max_length=100, default="sentence-transformers/all-MiniLM-L6-v2"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "paper_chat_chunks"
        unique_together = [("card", "chunk_index")]
        ordering = ["card", "chunk_index"]
        indexes = [
            models.Index(fields=["card", "last_accessed_at"]),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} for Card #{self.card_id}"


class ChatSession(models.Model):
    """
    A conversation session tied to a specific research paper card.
    design.md §5:
    - Multi-turn conversation history.
    - Summary generated after session for memory.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )
    card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name="chat_sessions"
    )
    scope_type = models.CharField(max_length=20, default="paper")  # "paper" or "topic"
    mode = models.CharField(max_length=20, default="qna")  # "qna" or "study_with"
    started_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    summary = models.TextField(blank=True, default="")

    class Meta:
        db_table = "chat_sessions"
        ordering = ["-started_at"]

    def __str__(self):
        return f"ChatSession #{self.pk} (Card #{self.card_id})"


class ChatMessage(models.Model):
    """
    One message in a paper chat session.
    Rule 12: Every cited chunk ID must have been retrieved and the quoted text must appear in it.
    design.md §5: Citations are tappable and show the quoted chunk.
    """

    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    # List of { "chunk_id": int, "quote": str, "claim": str }
    citations = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_messages"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"


# ---------------------------------------------------------------------------
# Card relations (dynamic links across research papers)
# ---------------------------------------------------------------------------


class CardRelation(models.Model):
    """
    Dynamic research paper link connecting related papers.
    Rule 56 & 57:
    - Flowing stream of dynamic research links (reusable link tiles, not nested cards).
    - Ingest-time dynamic linking binds new papers to existing corpus papers.
    """

    RELATION_TYPE_CHOICES = [
        ("shared_technique", "Shared Technique"),
        ("benchmark_comparison", "Benchmark Comparison"),
        ("topic_cluster", "Topic Cluster"),
        ("direct_citation", "Direct Citation"),
        ("follow_up", "Follow-up Work"),
    ]

    source_card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name="outgoing_relations"
    )
    target_card = models.ForeignKey(
        Card, on_delete=models.CASCADE, related_name="incoming_relations"
    )
    relation_type = models.CharField(
        max_length=40, choices=RELATION_TYPE_CHOICES, default="topic_cluster"
    )
    relation_label = models.CharField(
        max_length=200, help_text="Human-readable label, e.g. 'Shared Architecture: Transformers'"
    )
    similarity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "card_relations"
        unique_together = [("source_card", "target_card")]
        ordering = ["-similarity_score", "-created_at"]
        indexes = [
            models.Index(fields=["source_card", "-similarity_score"]),
        ]

    def __str__(self):
        return f"Card #{self.source_card_id} -> Card #{self.target_card_id} ({self.relation_type}: {self.relation_label})"


