"""
core/views_byok.py

API views for managing BYOK credentials and querying daily quota status.

Endpoints under /api/v1/core/credentials/:
  GET    /api/v1/core/credentials/         — list user's saved BYOK credentials (masked)
  POST   /api/v1/core/credentials/         — register or update a BYOK API key
  DELETE /api/v1/core/credentials/<id>/    — delete a BYOK credential
  GET    /api/v1/core/credentials/quota/   — check current daily personalized quota status
"""

from __future__ import annotations

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.llm.byok import get_daily_quota_status
from core.models import LLMCredential
from core.serializers_byok import LLMCredentialSerializer, QuotaStatusSerializer


def _resolve_user(request: Request) -> User:
    if request.user and request.user.is_authenticated:
        return request.user
    user, _ = User.objects.get_or_create(username="demo_reader", defaults={"email": "demo@ainews.local"})
    return user


class LLMCredentialListCreateView(APIView):
    """List or create BYOK credentials for the current user."""

    def get(self, request: Request) -> Response:
        user = _resolve_user(request)
        creds = LLMCredential.objects.filter(user=user).order_by("-is_default", "provider")
        serializer = LLMCredentialSerializer(creds, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        user = _resolve_user(request)
        serializer = LLMCredentialSerializer(data=request.data)
        if serializer.is_valid():
            credential = serializer.save(user=user)
            return Response(LLMCredentialSerializer(credential).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LLMCredentialDetailView(APIView):
    """Delete a user's BYOK credential."""

    def delete(self, request: Request, pk: int) -> Response:
        user = _resolve_user(request)
        credential = get_object_or_404(LLMCredential, pk=pk, user=user)
        credential.delete()
        return Response({"detail": "Credential deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class QuotaStatusView(APIView):
    """Retrieve remaining daily personalized quota and BYOK status."""

    def get(self, request: Request) -> Response:
        user = _resolve_user(request)
        session_id = request.session.session_key or request.headers.get("X-Session-ID", "")
        status_data = get_daily_quota_status(user, session_id=session_id)
        serializer = QuotaStatusSerializer(status_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

