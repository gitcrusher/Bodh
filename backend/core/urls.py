"""
core/urls.py

URL routes for core platform endpoints (BYOK credentials, quota).
"""

from django.urls import path

from core.views_byok import (
    LLMCredentialDetailView,
    LLMCredentialListCreateView,
    QuotaStatusView,
)

urlpatterns = [
    path("credentials/", LLMCredentialListCreateView.as_view(), name="credential_list_create"),
    path("credentials/<int:pk>/", LLMCredentialDetailView.as_view(), name="credential_detail"),
    path("credentials/quota/", QuotaStatusView.as_view(), name="quota_status"),
]

