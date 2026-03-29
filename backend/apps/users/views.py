from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.hashers import check_password
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import timedelta
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
@permission_classes([AllowAny])
def pin_login_view(request):
    try:
        pin = str(request.data.get("pin") or "").strip()
        if not pin.isdigit() or len(pin) < 4 or len(pin) > 6:
            return Response({"detail": "PIN inválido"}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        profiles = UserProfile.objects.select_related("user").filter(is_active=True).exclude(pin_hash="")
        locked_profile = profiles.filter(pin_locked_until__gt=now).first()
        if locked_profile and any(check_password(pin, p.pin_hash) for p in profiles):
            return Response({"detail": "PIN temporalmente bloqueado. Intenta de nuevo en unos segundos."}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        matched_profile = None
        for profile in profiles:
            if profile.pin_hash and check_password(pin, profile.pin_hash):
                matched_profile = profile
                break

        if matched_profile is None:
            profiles.filter(pin_locked_until__lte=now).update(pin_locked_until=None)
            for profile in profiles:
                profile.pin_failed_attempts = (profile.pin_failed_attempts or 0) + 1
                if profile.pin_failed_attempts >= 5:
                    profile.pin_locked_until = now + timedelta(seconds=30)
                    profile.pin_failed_attempts = 0
                profile.save(update_fields=["pin_failed_attempts", "pin_locked_until"])
            return Response({"detail": "PIN incorrecto"}, status=status.HTTP_401_UNAUTHORIZED)

        matched_profile.pin_failed_attempts = 0
        matched_profile.pin_locked_until = None
        matched_profile.save(update_fields=["pin_failed_attempts", "pin_locked_until"])
        login(request, matched_profile.user)
        return Response(
            {
                "id": matched_profile.user.id,
                "username": matched_profile.user.get_username(),
                "email": matched_profile.user.email,
                "role": matched_profile.role,
            }
        )
    except Exception:  # noqa: BLE001
        logger.exception("auth.pin_login.failed")
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
