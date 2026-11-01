"""Tests for StageLedger idempotency and version-gated processing."""

import pytest
from core.models import PipelineStageLedger
from core.pipeline.ledger import StageLedger


@pytest.mark.django_db
def test_stage_ledger_idempotency():
    ledger = StageLedger()
    payload = {"title": "Attention Is All You Need", "abstract": "Transformer model..."}

    # Before processing, check should return False
    assert not ledger.check("raw_item", 101, "summarize", payload, "1.0")

    # Mark done
    ledger.mark_done("raw_item", 101, "summarize", payload, "1.0")

    # Now check should return True (skip processing)
    assert ledger.check("raw_item", 101, "summarize", payload, "1.0")

    # Re-marking done does not crash (idempotent duplicate write)
    ledger.mark_done("raw_item", 101, "summarize", payload, "1.0")
    assert PipelineStageLedger.objects.filter(item_id=101, stage="summarize").count() == 1


@pytest.mark.django_db
def test_stage_ledger_logic_version_bump():
    ledger = StageLedger()
    payload = {"text": "some input"}

    ledger.mark_done("raw_item", 202, "triage", payload, "1.0")

    # v1.0 is done
    assert ledger.check("raw_item", 202, "triage", payload, "1.0")

    # Bumping logic_version to 1.1 allows reprocessing
    assert not ledger.check("raw_item", 202, "triage", payload, "1.1")
