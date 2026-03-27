from django.contrib.auth import authenticate, login, logout, get_user_model
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.users.models import UserProfile

logger = logging.getLogger(__name__)


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "admin" if user.is_superuser else "cashier", "is_active": True},
    )
    return profile


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf_view(request):
    try:
        get_token(request)
        return Response({"detail": "ok"})
    except Exception:  # noqa: BLE001
        logger.exception("auth.csrf.failed")
        return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    try:
        email = request.data.get("email")
        username = request.data.get("username")
        password = request.data.get("password")
        if not password or not (email or username):
            return Response({"detail": "Missing credentials"}, status=status.HTTP_400_BAD_REQUEST)

        user = None
        if email and not username:
            user_model = get_user_model()
            user = user_model.objects.filter(email__iexact=email).first()
            if user:
                username = user.get_username()

        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        profile = _get_or_create_profile(user)
        if not profile.is_active:
            return Response({"detail": "User inactive"}, status=status.HTTP_403_FORBIDDEN)

        login(request, user)
        return Response(
            {
                "id": user.id,
                "username": user.get_username(),
                "email": user.email,
                "role": profile.role,
            }
        )
    except Exception:  # noqa: BLE001
        logger.exception("auth.login.failed")
        return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def logout_view(request):
    try:
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception:  # noqa: BLE001
        logger.exception("auth.logout.failed")
        return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
def me_view(request):
    try:
        if not request.user.is_authenticated:
            return Response({"detail": "Not authenticated"}, status=status.HTTP_401_UNAUTHORIZED)
        profile = _get_or_create_profile(request.user)
        if not profile.is_active:
            return Response({"detail": "User inactive"}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "id": request.user.id,
                "username": request.user.get_username(),
                "email": request.user.email,
                "role": profile.role,
            }
        )
    except Exception:  # noqa: BLE001
        logger.exception("auth.me.failed")
        return Response({"detail": "Internal error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
