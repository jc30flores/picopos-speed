from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone

SESSION_LOGIN_AT_KEY = "auth_login_at"
SESSION_LAST_ACTIVITY_KEY = "auth_last_activity"

AUTH_SESSION_EXEMPT_EXACT = {
    "/api/auth/csrf",
    "/api/auth/login",
    "/api/auth/pin-login",
    "/api/auth/logout",
}

SESSION_SECURITY_EXEMPT_PREFIXES = (
    "/api/public/",
    "/static/",
    "/media/",
    "/assets/",
)

SESSION_SECURITY_EXEMPT_EXACT = {
    "/api/public",
    "/api/public/appearance",
    "/api/public/manifest.webmanifest",
    "/api/public/pwa/metadata",
    "/api/public/pwa/favicon.ico",
    "/api/public/pwa/icon-192.png",
    "/api/public/pwa/icon-512.png",
    "/api/public/pwa/apple-touch-icon.png",
    "/api/public/pwa/icon-maskable-512.png",
    "/api/public/pwa/share-image.png",
    "/favicon.ico",
    "/health",
    "/healthz",
}


@dataclass(frozen=True)
class SessionExpiryResult:
    expired: bool
    code: str = ""
    detail: str = ""


def _now_ts() -> int:
    return int(timezone.now().timestamp())


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_session_security_exempt_path(path: str) -> bool:
    normalized = (path or "/").split("?", 1)[0].rstrip("/") or "/"
    if normalized in AUTH_SESSION_EXEMPT_EXACT:
        return True
    if normalized in SESSION_SECURITY_EXEMPT_EXACT:
        return True
    return any(normalized.startswith(prefix) for prefix in SESSION_SECURITY_EXEMPT_PREFIXES)


def initialize_session_security(request) -> None:
    now = _now_ts()
    request.session[SESSION_LOGIN_AT_KEY] = now
    request.session[SESSION_LAST_ACTIVITY_KEY] = now
    request.session.set_expiry(settings.GASTROPOSV_SESSION_MAX_AGE_SECONDS)


def validate_session_security(request) -> SessionExpiryResult:
    now = _now_ts()
    login_at = _as_int(request.session.get(SESSION_LOGIN_AT_KEY))
    last_activity = _as_int(request.session.get(SESSION_LAST_ACTIVITY_KEY))

    if login_at is None or last_activity is None:
        return SessionExpiryResult(
            expired=True,
            code="session_expired",
            detail="Tu sesión expiró. Ingresa nuevamente.",
        )

    if now - login_at > settings.GASTROPOSV_SESSION_MAX_AGE_SECONDS:
        return SessionExpiryResult(
            expired=True,
            code="max_session_age",
            detail="Tu sesión venció por seguridad. Ingresa nuevamente.",
        )

    if now - last_activity > settings.GASTROPOSV_IDLE_TIMEOUT_SECONDS:
        return SessionExpiryResult(
            expired=True,
            code="idle_timeout",
            detail="Tu sesión se cerró por inactividad.",
        )

    request.session[SESSION_LAST_ACTIVITY_KEY] = now
    return SessionExpiryResult(expired=False)


def session_expired_response(request, result: SessionExpiryResult) -> JsonResponse:
    logout(request)
    return JsonResponse(
        {
            "detail": result.detail or "Tu sesión expiró. Ingresa nuevamente.",
            "code": result.code or "session_expired",
        },
        status=401,
    )
