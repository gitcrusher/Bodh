"""Core admin — register core models for visibility in Django admin."""

from django.contrib import admin

from core.models import AgentRun, EvalRun, FeatureFlag, PipelineStageLedger, RetentionRule


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ["agent_name", "provider_used", "status", "input_tokens", "output_tokens", "latency_ms", "created_at"]
    list_filter = ["agent_name", "provider_used", "status"]
    search_fields = ["agent_name", "input_ref"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]


@admin.register(PipelineStageLedger)
class PipelineStageLedgerAdmin(admin.ModelAdmin):
    list_display = ["item_type", "item_id", "stage", "logic_version", "status", "completed_at"]
    list_filter = ["item_type", "stage", "status"]
    ordering = ["-completed_at"]


@admin.register(EvalRun)
class EvalRunAdmin(admin.ModelAdmin):
    list_display = ["module", "suite", "logic_version", "metric", "value", "n_items", "created_at"]
    list_filter = ["module", "suite"]
    ordering = ["-created_at"]


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ["name", "enabled", "updated_at"]
    list_editable = ["enabled"]


@admin.register(RetentionRule)
class RetentionRuleAdmin(admin.ModelAdmin):
    list_display = ["module", "rule_key", "table_name", "active", "last_run_at"]
    list_filter = ["module", "active"]
