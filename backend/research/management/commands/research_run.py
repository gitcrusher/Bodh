"""
research/management/commands/research_run.py

Management command: run the daily research ingestion pipeline.

Usage:
    python manage.py research_run
    python manage.py research_run --source-id 1
    python manage.py research_run --dry-run          # no HTTP calls, smoke-tests graph
    python manage.py research_run --all-sources      # run all active sources

This command is safe to re-run: the stage ledger ensures each item is processed
at most once per logic_version. If the run crashes partway, re-running picks up
where it left off.
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from research.models import Source


class Command(BaseCommand):
    help = "Run the daily research ingestion pipeline for one or all active sources."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-id",
            type=int,
            default=None,
            help="Run only the source with this primary key.",
        )
        parser.add_argument(
            "--all-sources",
            action="store_true",
            default=False,
            help="Run all active sources (default if --source-id not given).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Build graph but skip HTTP fetch calls. Useful for smoke-testing.",
        )

    def handle(self, *args, **options):
        from research.graph import run_daily_research

        dry_run: bool = options["dry_run"]
        source_id: int | None = options["source_id"]

        if source_id is not None:
            sources = list(Source.objects.filter(pk=source_id, active=True))
            if not sources:
                raise CommandError(f"No active source found with id={source_id}")
        else:
            sources = list(Source.objects.filter(active=True))
            if not sources:
                self.stdout.write(self.style.WARNING("No active sources found. Nothing to run."))
                return

        for source in sources:
            self.stdout.write(f"▶ Running source: {source.name} (id={source.pk})")
            summary = run_daily_research(source.pk, dry_run=dry_run)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Done — {summary.get('cards_written', 0)} card(s) written, "
                    f"{summary.get('tokens_used', 0)} tokens used, "
                    f"{len(summary.get('errors', []))} error(s)\n"
                    + (
                        "  Errors:\n    " + "\n    ".join(summary.get("errors", []))
                        if summary.get("errors")
                        else ""
                    )
                )
            )
