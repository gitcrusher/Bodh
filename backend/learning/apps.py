from django.apps import AppConfig


class LearningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "learning"
    verbose_name = "Learning — Knowledge Calibration & Personalization"

    def ready(self) -> None:
        # Wire up any signals if needed in future
        pass
