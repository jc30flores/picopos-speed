from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings


PLACEHOLDER_WORDS = (
    "replace-with",
    "changeme",
    "change-me",
    "placeholder",
    "example",
)

PLACEHOLDER_HOSTS = {
    "example.com",
    "www.example.com",
    "localhost",
    "127.0.0.1",
    "::1",
}


@dataclass(frozen=True)
class DTEConfigStatus:
    configured: bool
    base_url_ok: bool
    token_ok: bool
    reason: str
    base_url_state: str
    token_state: str


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _has_placeholder_text(value: str) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return False
    if lowered.startswith("<") and lowered.endswith(">"):
        return True
    return any(word in lowered for word in PLACEHOLDER_WORDS)


def validate_dte_base_url(value: str | None) -> tuple[bool, str]:
    raw = _clean(value)
    if not raw:
        return False, "missing_base_url"
    if _has_placeholder_text(raw):
        return False, "placeholder_base_url"
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        return False, "invalid_base_url"
    host = parsed.hostname.lower()
    if host in PLACEHOLDER_HOSTS or host.endswith(".invalid"):
        return False, "placeholder_base_url"
    return True, "configured"


def validate_dte_api_token(value: str | None) -> tuple[bool, str]:
    raw = _clean(value)
    if not raw:
        return False, "missing_api_token"
    if _has_placeholder_text(raw):
        return False, "placeholder_api_token"
    return True, "configured"


def get_dte_config_status(base_url: str | None = None, api_token: str | None = None) -> DTEConfigStatus:
    if base_url is None:
        base_url = getattr(settings, "DTE_BASE_URL", "")
    if api_token is None:
        api_token = getattr(settings, "DTE_API_TOKEN", "")

    base_url_ok, base_reason = validate_dte_base_url(base_url)
    token_ok, token_reason = validate_dte_api_token(api_token)
    configured = base_url_ok and token_ok
    reason = "configured"
    if not configured:
        reason = base_reason if not base_url_ok else token_reason
    return DTEConfigStatus(
        configured=configured,
        base_url_ok=base_url_ok,
        token_ok=token_ok,
        reason=reason,
        base_url_state=base_reason,
        token_state=token_reason,
    )
