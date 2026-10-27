"""WSGI config for ai_news project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_news.settings")

application = get_wsgi_application()
