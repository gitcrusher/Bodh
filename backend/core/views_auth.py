"""
core/views_auth.py

Authentication endpoints for Rule 65 (OKF):
  POST /api/v1/core/auth/register/ — create user + return token
  POST /api/v1/core/auth/login/    — authenticate user + return token
  GET  /api/v1/core/auth/me/       — return current user profile + cycle
  POST /api/v1/core/auth/logout/   — revoke current auth token
"""

from datetime import timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "").strip()
        email = request.data.get("email", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "A user with that username already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if email and User.objects.filter(email=email).exists():
            return Response(
                {"error": "A user with that email already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
        )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Allow login by email as well
        if "@" in username:
            user_obj = User.objects.filter(email=username).first()
            if user_obj:
                username = user_obj.username

        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
            }
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined,
        }

        # Attach knowledge cycle info if available
        if hasattr(user, "knowledge_cycle"):
            cycle = user.knowledge_cycle
            data["cycle"] = {
                "is_quiz_due": cycle.is_quiz_due,
                "next_quiz_due_at": cycle.next_quiz_due_at,
                "last_quiz_completed_at": cycle.last_quiz_completed_at,
                "is_gated": cycle.is_gated,
            }

        return Response(data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        if hasattr(request.user, "auth_token"):
            request.user.auth_token.delete()
        return Response({"status": "logged_out"})

