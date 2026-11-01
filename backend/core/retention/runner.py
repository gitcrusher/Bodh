"""
Retention runner — executes registered retention rules per module.

Rule (rules.md rule 38): "Every table that grows has a registered retention rule."
Rule (memory.md section 5): Retention table by table.

Modules register their rules via register_rule() at startup.
The management command `run_retention` calls run_all().
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Callable

from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Handler registry — maps rule_key → callable
# ---------------------------------------------------------------------------
_handlers: dict[str, Callable[[dict], int]] = {}


def register_handler(rule_key: str, handler: Callable[[dict], int]) -> None:
    """
    Register a retention handler.
    handler(params: dict) -> int (number of rows affected)
    """
    _handlers[rule_key] = handler
    logger.debug("Retention handler registered: %s", rule_key)


# ---------------------------------------------------------------------------
# Built-in handlers (core tables)
# ---------------------------------------------------------------------------
def _handle_clear_agent_runs_output(params: dict) -> int:
    """
    Clear full output/tool_calls from AgentRun rows older than
    `full_retention_days` (keep metadata only — agent_name, tokens, etc.)
    """
    from core.models import AgentRun  # lazy

    days = params.get("full_retention_days", 14)
    cutoff = timezone.now() - timedelta(days=days)
    count = AgentRun.objects.filter(created_at__lt=cutoff).exclude(output="").update(
        output="", tool_calls=[]
    )
    logger.info("Retention: cleared output from %d old AgentRun rows", count)
    return count


def _handle_prune_ledger(params: dict) -> int:
    """
    Remove ledger rows older than `max_age_days` EXCEPT ingest rows
    (which must stay permanently to block re-fetching).
    """
    from core.models import PipelineStageLedger  # lazy

    days = params.get("max_age_days", 365)
    cutoff = timezone.now() - timedelta(days=days)
    count = PipelineStageLedger.objects.filter(
        completed_at__lt=cutoff
    ).exclude(
        stage="ingest"
    ).delete()[0]
    logger.info("Retention: pruned %d old ledger rows", count)
    return count


# Register built-in handlers
register_handler("clear_agent_runs_output", _handle_clear_agent_runs_output)
register_handler("prune_ledger", _handle_prune_ledger)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_all() -> dict[str, int]:
    """
    Execute all active retention rules from the DB.
    Returns {rule_key: rows_affected}.
    """
    from core.models import RetentionRule  # lazy

    results: dict[str, int] = {}
    rules = RetentionRule.objects.filter(active=True)

    for rule in rules:
        handler = _handlers.get(rule.rule_key)
        if handler is None:
            logger.warning(
                "Retention: no handler for rule_key=%r (module=%s). Skipping.",
                rule.rule_key,
                rule.module,
            )
            continue
        try:
            affected = handler(rule.params)
            results[rule.rule_key] = affected
            rule.last_run_at = timezone.now()
            rule.save(update_fields=["last_run_at"])
        except Exception as exc:
            logger.error(
                "Retention handler %r failed: %s", rule.rule_key, exc, exc_info=True
            )
            results[rule.rule_key] = -1

    return results


def ensure_core_rules_exist() -> None:
    """
    Idempotently create the core retention rules in the DB.
    Called from the research app's data migration or management command.
    """
    from core.models import RetentionRule  # lazy

    core_rules = [
        {
            "module": "core",
            "table_name": "agent_runs",
            "rule_key": "clear_agent_runs_output",
            "description": "Clear full output from AgentRun rows older than full_retention_days",
            "params": {"full_retention_days": 14},
        },
        {
            "module": "core",
            "table_name": "pipeline_stage_ledger",
            "rule_key": "prune_ledger",
            "description": "Prune old non-ingest ledger rows",
            "params": {"max_age_days": 365},
        },
    ]

    for rule_data in core_rules:
        RetentionRule.objects.get_or_create(
            module=rule_data["module"],
            rule_key=rule_data["rule_key"],
            defaults=rule_data,
        )
