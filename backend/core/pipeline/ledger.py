"""
Stage ledger — enforces the never-reprocess rule.

Rule (rules.md rule 4-6, design doc 14.3):
  "Never reprocess the same input with the same logic_version."
  A UNIQUE index on (item_type, item_id, stage, input_hash, logic_version) is the gate.
  Before any stage runs, call ledger.check(); if it returns True, skip.
  After success, call ledger.mark_done().
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)


def _make_hash(payload: Any) -> str:
    """SHA-256 of the canonical JSON representation of payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class StageLedger:
    """
    Thin wrapper around the PipelineStageLedger model.
    Import the model lazily to avoid circular imports during app startup.
    """

    def check(
        self,
        item_type: str,
        item_id: int,
        stage: str,
        input_payload: Any,
        logic_version: str,
    ) -> bool:
        """
        Return True if this (item, stage, input, version) was already
        processed successfully — the stage should be SKIPPED.
        """
        from core.models import PipelineStageLedger  # lazy

        input_hash = _make_hash(input_payload)
        return PipelineStageLedger.objects.filter(
            item_type=item_type,
            item_id=item_id,
            stage=stage,
            input_hash=input_hash,
            logic_version=logic_version,
            status="done",
        ).exists()

    def mark_done(
        self,
        item_type: str,
        item_id: int,
        stage: str,
        input_payload: Any,
        logic_version: str,
    ) -> None:
        """Record a successful stage completion. Silently ignores duplicate writes."""
        from core.models import PipelineStageLedger  # lazy

        input_hash = _make_hash(input_payload)
        try:
            with transaction.atomic():
                PipelineStageLedger.objects.create(
                    item_type=item_type,
                    item_id=item_id,
                    stage=stage,
                    input_hash=input_hash,
                    logic_version=logic_version,
                    status="done",
                )
        except IntegrityError:
            # Already exists — idempotent, ignore
            logger.debug(
                "Ledger: duplicate done entry ignored for %s:%d stage=%s v=%s",
                item_type,
                item_id,
                stage,
                logic_version,
            )

    def mark_failed(
        self,
        item_type: str,
        item_id: int,
        stage: str,
        input_payload: Any,
        logic_version: str,
    ) -> None:
        """Record a failed stage (will be retried on next run)."""
        from core.models import PipelineStageLedger  # lazy

        input_hash = _make_hash(input_payload)
        PipelineStageLedger.objects.update_or_create(
            item_type=item_type,
            item_id=item_id,
            stage=stage,
            input_hash=input_hash,
            logic_version=logic_version,
            defaults={"status": "failed"},
        )

    def mark_deferred(
        self,
        item_type: str,
        item_id: int,
        stage: str,
        input_payload: Any,
        logic_version: str,
    ) -> None:
        """Record a deferred stage (e.g. budget exceeded; retry next run)."""
        from core.models import PipelineStageLedger  # lazy

        input_hash = _make_hash(input_payload)
        PipelineStageLedger.objects.update_or_create(
            item_type=item_type,
            item_id=item_id,
            stage=stage,
            input_hash=input_hash,
            logic_version=logic_version,
            defaults={"status": "deferred"},
        )

    def compute_hash(self, payload: Any) -> str:
        """Public utility so callers can log or compare hashes."""
        return _make_hash(payload)


# Module-level singleton
ledger = StageLedger()