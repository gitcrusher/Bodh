"""
Core platform models.

Rule: core never imports from a module app. Modules import from core.
"""

from django.db import models
from django.utils import timezone


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
