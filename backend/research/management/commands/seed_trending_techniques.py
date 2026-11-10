"""
research/management/commands/seed_trending_techniques.py

Step 7 — Seeds canonical trending techniques and their literature links (Semantic Scholar / OpenAlex).
"""

from django.core.management.base import BaseCommand
from research.technique_grounding_service import TechniqueGroundingService
from research.models import TrendingTechnique, TechniqueLiteratureLink


class Command(BaseCommand):
    help = "Seed canonical trending techniques and literature grounding links (Step 7, Rule 52)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding canonical trending techniques and literature links...")
        created = TechniqueGroundingService.seed_default_techniques()
        total_techs = TrendingTechnique.objects.count()
        total_links = TechniqueLiteratureLink.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded trending techniques! "
                f"Created {created} new, total {total_techs} techniques with {total_links} literature links."
            )
        )

