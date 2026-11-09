"""
learning/management/commands/seed_questions.py

Seeds Topics and QuizQuestions from the golden question bank.
Safe to re-run (idempotent via get_or_create).

Usage:
    python manage.py seed_questions
    python manage.py seed_questions --clear   # wipe existing first
"""

from django.core.management.base import BaseCommand

from learning.evals.golden_questions import GOLDEN_QUESTIONS
from learning.models import QuizQuestion, Topic

TOPIC_DISPLAY_NAMES = {
    "transformers": "Transformer Architecture",
    "diffusion_models": "Diffusion Models",
    "rag": "Retrieval-Augmented Generation",
    "fine_tuning": "Fine-Tuning & Alignment",
}


class Command(BaseCommand):
    help = "Seed Topics and QuizQuestions from the golden question bank"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing questions before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            QuizQuestion.objects.all().delete()
            Topic.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared all topics and questions."))

        created_topics = 0
        created_questions = 0

        for item in GOLDEN_QUESTIONS:
            topic_slug = item["topic_slug"]
            display_name = TOPIC_DISPLAY_NAMES.get(topic_slug, topic_slug.replace("_", " ").title())

            topic, t_created = Topic.objects.get_or_create(
                slug=topic_slug,
                defaults={
                    "display_name": display_name,
                    "is_seeded": True,
                },
            )
            if t_created:
                created_topics += 1

            _, q_created = QuizQuestion.objects.get_or_create(
                topic=topic,
                difficulty=item["difficulty"],
                stem=item["stem"],
                defaults={
                    "options": item["options"],
                    "correct_index": item["correct_index"],
                    "explanation": item.get("explanation", ""),
                    "is_active": True,
                },
            )
            if q_created:
                created_questions += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeding complete: {created_topics} topics created, "
                f"{created_questions} questions created."
            )
        )
