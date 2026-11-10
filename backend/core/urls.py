"""
core/urls.py

URL routes for core platform endpoints (Auth, BYOK credentials, quota).
"""

from django.urls import path

from core.views_auth import LoginView, LogoutView, MeView, RegisterView
from core.views_byok import (
    LLMCredentialDetailView,
    LLMCredentialListCreateView,
    QuotaStatusView,
)

urlpatterns = [
    # Auth endpoints (Rule 65)
    path("auth/register/", RegisterView.as_view(), name="auth_register"),
    path("auth/login/", LoginView.as_view(), name="auth_login"),
    path("auth/me/", MeView.as_view(), name="auth_me"),
    path("auth/logout/", LogoutView.as_view(), name="auth_logout"),
    # BYOK credentials
    path("credentials/", LLMCredentialListCreateView.as_view(), name="credential_list_create"),
    path("credentials/<int:pk>/", LLMCredentialDetailView.as_view(), name="credential_detail"),
    path("credentials/quota/", QuotaStatusView.as_view(), name="quota_status"),
]
