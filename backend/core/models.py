"""
Core platform models.

Rule: core never imports from a module app. Modules import from core.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from core.encryption import decrypt_secret, encrypt_secret, mask_api_key


# ---------------------------------------------------------------------------
# Agent runs — observability for every LLM step
# ---------------------------------------------------------------------------
class AgentRun(models.Model):
    """Logged by run_step() for every LLM call in the pipeline."""

    agent_name = models.CharField(max_length=100)
    # Opaque reference to the item being processed (e.g. "raw_item:42")
    input_ref = models.CharField(max_length=200, blank=True)
    # Full output and tool_calls kept for AGENT_RUNS_FULL_RETENTION_DAYS,
    # then cleared by the retention runner (only metadata stays).
    output = models.TextField(blank=True)
    tool_calls = models.JSONField(default=list)
    latency_ms = models.IntegerField(null=True, blank=True)
    provider_used = models.CharField(max_length=50, blank=True)
    prompt_version = models.CharField(max_length=50, blank=True)
    source_ids = models.JSONField(default=list)
    fallback_used = models.BooleanField(default=False)
    input_tokens = models.IntegerField(null=True, blank=True)
    output_tokens = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        default="done",
        choices=[
            ("done", "Done"),
            ("failed_generation", "Failed Generation"),
            ("schema_error", "Schema Error"),
            ("provider_down", "Provider Down"),
        ],
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "agent_runs"
        indexes = [
            models.Index(fields=["agent_name", "created_at"]),
            models.Index(fields=["input_ref"]),
        ]

    def __str__(self) -> str:
        return f"{self.agent_name} [{self.provider_used}] @ {self.created_at:%Y-%m-%d %H:%M}"


# ---------------------------------------------------------------------------
# Pipeline stage ledger — "never reprocess the same input at the same logic_version"
# ---------------------------------------------------------------------------
class PipelineStageLedger(models.Model):
    """
    One row per (item, stage, input_hash, logic_version).
    A stage checks this before running; if a done row exists, it skips.
    UNIQUE index enforces idempotency at the DB level.
    """

    item_type = models.CharField(
        max_length=30,
        choices=[
            ("raw_item", "Raw Item"),
            ("card", "Card"),
            ("technique", "Technique"),
            ("session", "Session"),
        ],
    )
    item_id = models.BigIntegerField()
    stage = models.CharField(
        max_length=50,
        choices=[
            ("ingest", "Ingest"),
            ("embed", "Embed"),
            ("triage", "Triage"),
            ("summarize", "Summarize"),
            ("validity", "Validity"),
            ("canon_check", "Canon Check"),
            ("grounding", "Grounding"),
            ("chunk", "Chunk"),
            ("graph_link", "Graph Link"),
        ],
    )
    # SHA-256 hex of the input payload used for this stage
    input_hash = models.CharField(max_length=64)
    logic_version = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=[
            ("done", "Done"),
            ("failed", "Failed"),
            ("deferred", "Deferred"),
        ],
        default="done",
    )
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "pipeline_stage_ledger"
        constraints = [
            models.UniqueConstraint(
                fields=["item_type", "item_id", "stage", "input_hash", "logic_version"],
                name="uq_ledger_stage",
            )
        ]
        indexes = [
            models.Index(fields=["item_type", "item_id", "stage"]),
            models.Index(fields=["completed_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.item_type}:{self.item_id} / {self.stage} / v{self.logic_version} [{self.status}]"


# ---------------------------------------------------------------------------
# Eval runs — history of evaluation suite results
# ---------------------------------------------------------------------------
class EvalRun(models.Model):
    """One row per metric per suite run. Full history enables regression queries."""

    module = models.CharField(max_length=50)       # e.g. "research"
    suite = models.CharField(max_length=100)        # e.g. "summarizer_golden"
    logic_version = models.CharField(max_length=20)
    metric = models.CharField(max_length=100)       # e.g. "entity_support_rate"
    value = models.FloatField()
    n_items = models.IntegerField()                 # Always record item count
    judge_model = models.CharField(max_length=100, blank=True)
    # Measured Cohen's kappa vs. human labels (blank until calibrated)
    judge_human_agreement = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "eval_runs"
        indexes = [
            models.Index(fields=["module", "suite", "logic_version", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.module}/{self.suite} {self.metric}={self.value:.3f} (n={self.n_items})"


# ---------------------------------------------------------------------------
# Feature flags — DB-level flags, overriding the bootstrap defaults in settings
# ---------------------------------------------------------------------------
class FeatureFlag(models.Model):
    """
    Runtime feature toggles. Modules ship dormant (enabled=False) and
    are enabled here after their evals pass (section 5.4 rule 5).
    """

    name = models.CharField(max_length=100, unique=True)
    enabled = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feature_flags"

    def __str__(self) -> str:
        state = "ON" if self.enabled else "OFF"
        return f"{self.name} [{state}]"


# ---------------------------------------------------------------------------
# Retention rules — registered by modules, executed by the retention runner
# ---------------------------------------------------------------------------
class RetentionRule(models.Model):
    """
    Each module registers its retention rules here.
    The retention runner queries this table and executes the appropriate
    cleanup SQL or ORM call on schedule.
    """

    module = models.CharField(max_length=50)
    table_name = models.CharField(max_length=100)
    rule_key = models.CharField(max_length=100)   # e.g. "clear_raw_content"
    description = models.TextField(blank=True)
    # JSON params passed to the runner's handler (e.g. {"grace_days": 7})
    params = models.JSONField(default=dict)
    active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "retention_rules"
        unique_together = [("module", "rule_key")]

    def __str__(self) -> str:
        return f"{self.module}/{self.rule_key} ({'active' if self.active else 'inactive'})"


# ---------------------------------------------------------------------------
# LLM credentials (BYOK) — encrypted at rest, scoped per user
# ---------------------------------------------------------------------------
class LLMCredential(models.Model):
    """
    Bring-Your-Own-Key (BYOK) credentials table.
    Enforces Rule 39 & Step 4:
    - Encrypted at rest via Fernet.
    - Scoped per user.
    - Personalization (deep-dive rewrites, paper chat) uses this key when present.
    """

    PROVIDER_CHOICES = [
        ("gemini", "Google Gemini"),
        ("groq", "Groq"),
        ("anthropic", "Anthropic Claude"),
        ("openai", "OpenAI"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="llm_credentials")
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    encrypted_api_key = models.TextField()
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "llm_credentials"
        unique_together = [("user", "provider")]
        indexes = [
            models.Index(fields=["user", "is_default"]),
        ]

    def set_api_key(self, plain_key: str) -> None:
        """Encrypts and sets the plaintext API key."""
        self.encrypted_api_key = encrypt_secret(plain_key.strip())

    def get_api_key(self) -> str:
        """Decrypts and returns the plaintext API key."""
        return decrypt_secret(self.encrypted_api_key)

    @property
    def masked_key(self) -> str:
        """Returns safe masked representation for UI presentation."""
        plain = self.get_api_key()
        return mask_api_key(plain)

    def __str__(self) -> str:
        return f"User {self.user_id} - {self.provider} ({self.masked_key})"


# ---------------------------------------------------------------------------
# Daily shared quota usage — caps personalized calls for users without BYOK
# ---------------------------------------------------------------------------
class DailyPersonalizedQuota(models.Model):
    """
    Tracks daily personalized LLM requests (deep-dive rewrites, paper chat)
    performed under the shared owner keys when user hasn't added a BYOK key.
    Design Doc §12: Caps at 5 free personalized calls per day.
    """

    DEFAULT_DAILY_CAP = 5

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name="quota_usage")
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    date = models.DateField(default=timezone.now)
    call_count = models.IntegerField(default=0)

    class Meta:
        db_table = "daily_personalized_quota"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                condition=models.Q(user__isnull=False),
                name="uq_user_quota_date",
            ),
            models.UniqueConstraint(
                fields=["session_id", "date"],
                condition=models.Q(session_id__gt=""),
                name="uq_session_quota_date",
            ),
        ]

    def increment(self) -> int:
        self.call_count += 1
        self.save(update_fields=["call_count"])
        return self.call_count

    def is_capped(self, limit: int = DEFAULT_DAILY_CAP) -> bool:
        return self.call_count >= limit

    def __str__(self) -> str:
        target = f"User {self.user_id}" if self.user_id else f"Session {self.session_id}"
        return f"{target} @ {self.date}: {self.call_count}/{self.DEFAULT_DAILY_CAP}"

