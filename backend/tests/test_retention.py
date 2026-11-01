"""Tests for retention runner and cleanup rules."""

from datetime import timedelta
import pytest
from django.utils import timezone
from core.models import AgentRun, PipelineStageLedger, RetentionRule
from core.retention import runner


@pytest.mark.django_db
def test_retention_clear_agent_runs_output():
    now = timezone.now()
    old_time = now - timedelta(days=20)
    recent_time = now - timedelta(days=2)

    old_run = AgentRun.objects.create(
        agent_name="summarizer",
        output="Long output text",
        tool_calls=[{"name": "fetch"}],
        created_at=old_time,
    )
    # Update created_at directly because auto_now_add or default might override
    AgentRun.objects.filter(id=old_run.id).update(created_at=old_time)

    recent_run = AgentRun.objects.create(
        agent_name="summarizer",
        output="Recent output text",
        tool_calls=[],
        created_at=recent_time,
    )

    # Run retention handler with 14-day cutoff
    affected = runner._handle_clear_agent_runs_output({"full_retention_days": 14})
    assert affected == 1

    old_run.refresh_from_db()
    assert old_run.output == ""
    assert old_run.tool_calls == []

    recent_run.refresh_from_db()
    assert recent_run.output == "Recent output text"


@pytest.mark.django_db
def test_retention_prune_ledger_preserves_ingest():
    now = timezone.now()
    old_time = now - timedelta(days=400)

    # Ingest stage ledger row (must stay permanently)
    ingest_row = PipelineStageLedger.objects.create(
        item_type="raw_item",
        item_id=1,
        stage="ingest",
        input_hash="hash1",
        logic_version="1.0",
        completed_at=old_time,
    )
    PipelineStageLedger.objects.filter(id=ingest_row.id).update(completed_at=old_time)

    # Summarize stage ledger row (should be pruned)
    summarize_row = PipelineStageLedger.objects.create(
        item_type="raw_item",
        item_id=1,
        stage="summarize",
        input_hash="hash2",
        logic_version="1.0",
        completed_at=old_time,
    )
    PipelineStageLedger.objects.filter(id=summarize_row.id).update(completed_at=old_time)

    # Run pruning handler with 365-day cutoff
    pruned = runner._handle_prune_ledger({"max_age_days": 365})
    assert pruned == 1

    assert PipelineStageLedger.objects.filter(id=ingest_row.id).exists()
    assert not PipelineStageLedger.objects.filter(id=summarize_row.id).exists()
