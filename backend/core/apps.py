"""Core app configuration."""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Platform Core"

    def ready(self) -> None:
        """Import signals and initialize singletons on startup."""
        # Warm up the embedding service (downloads model on first run)
        from core.embedding.service import embedding_service  # noqa: F401
