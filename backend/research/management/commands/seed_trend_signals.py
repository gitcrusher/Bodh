"""
management/commands/seed_trend_signals.py

Populates curated AI/ML seed accounts for Reddit, Bluesky, and Mastodon
and generates initial discussion trend signals for existing frontline cards.

Usage:
  python manage.py seed_trend_signals
"""

from django.core.management.base import BaseCommand
from research.models import Card, PaperTrendSignal, TrendSeedAccount
from research.trend_service import TrendService


class Command(BaseCommand):
    help = "Seed curated trend accounts and generate trend signals for cards"

    def handle(self, *args, **options):
        self.stdout.write("Seeding curated trend seed accounts (Reddit, Bluesky, Mastodon)...")
        created_seeds = TrendService.seed_default_accounts()
        total_seeds = TrendSeedAccount.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded {created_seeds} new accounts. Total seed accounts in DB: {total_seeds}"
            )
        )

        cards = Card.objects.all()
        self.stdout.write(f"Generating trend signals for {cards.count()} cards...")
        total_signals = 0
        for card in cards:
            signals = TrendService.generate_contextual_signals(card)
            total_signals += len(signals)

        db_signals = PaperTrendSignal.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated {total_signals} trend signals. Total PaperTrendSignal rows in DB: {db_signals}"
            )
        )

