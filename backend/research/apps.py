"""research/apps.py"""

from django.apps import AppConfig


class ResearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "research"
    label = "research"

    def ready(self):
        # Register the research module's retention rules with the core runner.
        # Import here (not at module level) to avoid circular imports at startup.
        # Guard against the pre-migration state where tables don't exist yet.
        try:
            from research.retention import register_research_retention  # noqa: F401

            register_research_retention()
        except Exception:  # noqa: BLE001 — DB not ready during makemigrations
            pass
