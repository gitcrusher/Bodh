"""ASGI config for ai_news project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_news.settings")

application = get_asgi_application()
