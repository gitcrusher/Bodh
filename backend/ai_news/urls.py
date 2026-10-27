"""URL configuration for ai_news project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
]

# Conditionally include research routes once the research app is installed
try:
    import research.urls  # noqa: F401
    urlpatterns.append(path("api/v1/research/", include("research.urls")))
except ImportError:
    pass

