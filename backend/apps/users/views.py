from django.contrib.auth import authenticate, login, logout, get_user_model
from django.conf import settings
from django.middleware.csrf import get_token
from django.core.cache import cache
from django.views.decorators.csrf import ensure_csrf_cookie
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes, renderer_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from apps.users.models import UserProfile
from apps.users.pin_utils import find_active_users_matching_pin, is_valid_pin_format, user_matches_pin

logger = logging.getLogger(__name__)


ROLE_LANDING_ROUTE = {
    "kitchen": "/kitchen",
    "kiosk": "/kiosk",
    "worker": "/",
}


def _json_response(payload, status_code=status.HTTP_200_OK):
    return Response(payload, status=status_code, content_type="application/json")


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "admin" if user.is_superuser else "cashier", "is_active": True},
    )
    return profile


def _build_auth_payload(user, role: str):
    profile_payload = {
        "role": role,
        "redirect_to": ROLE_LANDING_ROUTE.get(role, "/"),
    }
    user_payload = {
        "id": user.id,
        "username": user.get_username(),
        "email": user.email,
        "is_superuser": bool(user.is_superuser),
        "is_staff": bool(user.is_staff),
    }
    return {
        # Legacy flat shape (frontend compatibility)
        **user_payload,
        **profile_payload,
        # Stable structured shape (new contract)
        "user": user_payload,
        "profile": profile_payload,
        "permissions": {},
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
@ensure_csrf_cookie
def csrf_view(request):
    try:
        get_token(request)
        return _json_response({"detail": "ok"})
    except Exception:  # noqa: BLE001
        logger.exception("auth.csrf.failed")
        return _json_response({"detail": "Internal error"}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
@parser_classes([JSONParser])
def login_view(request):
    try:
        email = request.data.get("email")
        username = request.data.get("username")
        password = str(request.data.get("password") or "").strip()
        if not password or not (email or username):
            return _json_response({"detail": "Missing credentials"}, status.HTTP_400_BAD_REQUEST)
        if not is_valid_pin_format(password):
            return _json_response({"detail": "La contraseña/PIN debe ser de 6 dígitos numéricos."}, status.HTTP_400_BAD_REQUEST)

        user = None
        if email and not username:
            user_model = get_user_model()
            user = user_model.objects.filter(email__iexact=email).first()
            if user:
                username = user.get_username()

        user = authenticate(request, username=username, password=password)
        if user is None:
            return _json_response({"detail": "Invalid credentials"}, status.HTTP_401_UNAUTHORIZED)

        profile = _get_or_create_profile(user)
        if not profile.is_active:
            return _json_response({"detail": "User inactive"}, status.HTTP_403_FORBIDDEN)

        login(request, user)
        return _json_response(_build_auth_payload(user, profile.role))
    except Exception:  # noqa: BLE001
        logger.exception("auth.login.failed")
        return _json_response({"detail": "Internal error"}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
@parser_classes([JSONParser])
def pin_login_view(request):
    try:
        pin = str(request.data.get("pin") or "").strip()
        pin_len = len(pin)
        leading_zero = bool(pin.startswith("0"))
        logger.info("auth.pin_login.attempt pin_len=%s leading_zero=%s ip=%s", pin_len, leading_zero, request.META.get("REMOTE_ADDR", "unknown"))
        if not is_valid_pin_format(pin):
            logger.warning("auth.pin_login.invalid_format pin_len=%s leading_zero=%s", pin_len, leading_zero)
            return Response(
                {"detail": "El PIN debe tener exactamente 6 dígitos numéricos."},
                status=status.HTTP_400_BAD_REQUEST,
                content_type="application/json",
            )

        client_ip = request.META.get("REMOTE_ADDR", "unknown")
        throttle_key = f"auth:pin-login:{client_ip}"
        attempts = cache.get(throttle_key, 0)
        if attempts >= 5:
            return Response(
                {"detail": "Demasiados intentos. Intenta de nuevo en 30 segundos."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                content_type="application/json",
            )

        matches = find_active_users_matching_pin(pin)
        if not matches:
            cache.set(throttle_key, attempts + 1, timeout=30)
            logger.warning("auth.pin_login.no_match pin_len=%s leading_zero=%s attempts=%s", pin_len, leading_zero, attempts + 1)
            return _json_response({"detail": "PIN incorrecto"}, status.HTTP_401_UNAUTHORIZED)
        if len(matches) > 1:
            logger.warning("auth.pin_login.duplicate pin_len=%s leading_zero=%s matches=%s", pin_len, leading_zero, len(matches))
            return Response(
                {"detail": "PIN duplicado. Cambie el PIN de uno de los usuarios."},
                status=status.HTTP_409_CONFLICT,
                content_type="application/json",
            )

        user = matches[0]

        profile = _get_or_create_profile(user)
        if not profile.is_active:
            logger.warning("auth.pin_login.inactive_user user_id=%s", user.id)
            return _json_response({"detail": "User inactive"}, status.HTTP_403_FORBIDDEN)

        cache.delete(throttle_key)
        login(request, user)
        session_key = getattr(request.session, "session_key", None)
        cookie_name = getattr(getattr(request, "session", None), "cookie_name", "sessionid")
        logger.info(
            "auth.pin_login.success user_id=%s role=%s session_key=%s session_cookie=%s secure=%s samesite=%s",
            user.id,
            profile.role,
            f"{str(session_key)[:8]}..." if session_key else "(empty)",
            cookie_name,
            request.is_secure(),
            getattr(settings, "SESSION_COOKIE_SAMESITE", "(na)"),
        )
        return _json_response(_build_auth_payload(user, profile.role))
    except Exception:  # noqa: BLE001
        logger.exception("auth.pin_login.failed")
        return _json_response({"detail": "Internal error"}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([AllowAny])
@renderer_classes([JSONRenderer])
def logout_view(request):
    try:
        if request.user.is_authenticated:
            logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT, content_type="application/json")
    except Exception:  # noqa: BLE001
        logger.exception("auth.logout.failed")
        return _json_response({"detail": "Internal error"}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@renderer_classes([JSONRenderer])
def me_view(request):
    try:
        if not request.user.is_authenticated:
            return _json_response({"detail": "Not authenticated"}, status.HTTP_401_UNAUTHORIZED)
        profile = _get_or_create_profile(request.user)
        if not profile.is_active:
            return _json_response({"detail": "User inactive"}, status.HTTP_403_FORBIDDEN)
        logger.debug(
            "auth.me.success user_id=%s session_key=%s",
            request.user.id,
            f"{str(getattr(request.session, 'session_key', ''))[:8]}...",
        )
        return _json_response(_build_auth_payload(request.user, profile.role))
    except Exception:  # noqa: BLE001
        logger.exception("auth.me.failed")
        return _json_response({"detail": "Internal error"}, status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def verify_privileged_pin_view(request):
    pin = str(request.data.get("pin") or "").strip()
    if not is_valid_pin_format(pin):
        return Response({"ok": False, "detail": "invalid_pin_format"}, status=status.HTTP_400_BAD_REQUEST)

    privileged_profiles = UserProfile.objects.select_related("user").filter(
        is_active=True,
        role__in=["admin", "manager"],
        user__is_active=True,
    )
    for profile in privileged_profiles:
        user = profile.user
        if user and user.check_password(pin):
            return Response({"ok": True, "role": profile.role.upper(), "user_id": user.id}, status=status.HTTP_200_OK)
    return Response({"ok": False, "detail": "invalid"}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(["POST"])
def authorize_price_change_view(request):
    pin = str(request.data.get("pin") or "").strip()
    client_ip = request.META.get("REMOTE_ADDR", "unknown")

    def _invalid():
        logger.warning(
            "auth.authorize_price_change.failed user_id=%s ip=%s",
            getattr(request.user, "id", None),
            client_ip,
        )
        return Response({"ok": False, "detail": "Código inválido"}, status=status.HTTP_401_UNAUTHORIZED)

    if not is_valid_pin_format(pin):
        return _invalid()

    privileged_profiles = UserProfile.objects.select_related("user").filter(
        is_active=True,
        role__in=["admin", "manager"],
        user__is_active=True,
    )
    for profile in privileged_profiles:
        user = profile.user
        if user and user_matches_pin(user, pin):
            return Response({"ok": True, "role": profile.role.upper()}, status=status.HTTP_200_OK)
    return _invalid()
