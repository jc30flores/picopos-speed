from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from apps.core.branch_profile import get_branch_profile, get_current_branch_id
from apps.core.models import SystemAppearanceSettings, TicketSettings


logger = logging.getLogger(__name__)

DEFAULT_APP_NAME = "GastroPOSV"
PROJECT_APP_NAME = "La Rosee POS"
PROJECT_SHORT_NAME = "La Rosee"
PWA_DESCRIPTION = "Sistema POS para restaurante"


def safe_hex(value: str | None, fallback: str = "#1F7A4D") -> str:
    cleaned = str(value or "").strip().upper()
    if len(cleaned) == 7 and cleaned.startswith("#"):
        try:
            int(cleaned[1:], 16)
            return cleaned
        except ValueError:
            return fallback
    return fallback


def short_name(name: str) -> str:
    cleaned = " ".join(name.split()).strip()
    if cleaned.lower().endswith(" pos"):
        cleaned = cleaned[:-4].strip()
    return cleaned[:18] or DEFAULT_APP_NAME


def app_name() -> str:
    try:
        profile = get_branch_profile(get_current_branch_id())
        configured = str(profile.get("emisor_nombre") or "").strip()
    except Exception:
        logger.warning("pwa.branch_profile_unavailable", exc_info=True)
        configured = ""
    return configured or PROJECT_APP_NAME or DEFAULT_APP_NAME


def ticket_logo_path() -> Path | None:
    try:
        settings = TicketSettings.objects.filter(pk=1).first()
        if not settings or not settings.ticket_logo:
            return None
        path = Path(settings.ticket_logo.path)
        return path if path.exists() else None
    except (OSError, ValueError):
        logger.warning("pwa.ticket_logo_path_unavailable", exc_info=True)
        return None


def branding_version(name: str, short: str, appearance: SystemAppearanceSettings, ticket_settings: TicketSettings | None) -> str:
    logo_name = ""
    logo_updated = ""
    if ticket_settings and ticket_settings.ticket_logo:
        logo_name = ticket_settings.ticket_logo.name or ""
        logo_updated = ticket_settings.updated_at.isoformat() if ticket_settings.updated_at else ""
    source = "|".join(
        [
            name,
            short,
            appearance.primary_color,
            appearance.updated_at.isoformat() if appearance.updated_at else "",
            logo_name,
            logo_updated,
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def get_public_pwa_metadata() -> dict[str, str | bool]:
    appearance, _ = SystemAppearanceSettings.objects.get_or_create(pk=1)
    ticket_settings = TicketSettings.objects.filter(pk=1).first()
    name = app_name()
    short = PROJECT_SHORT_NAME if name == PROJECT_APP_NAME else short_name(name)
    version = branding_version(name, short, appearance, ticket_settings)
    theme_color = safe_hex(getattr(appearance, "color_primary", None) or appearance.primary_color)
    return {
        "app_name": name,
        "short_name": short,
        "description": PWA_DESCRIPTION,
        "theme_color": theme_color,
        "background_color": "#0B1020",
        "display": "standalone",
        "orientation": "any",
        "start_url": "/",
        "scope": "/",
        "version": version,
        "has_customer_logo": bool(ticket_logo_path()),
        "manifest_url": f"/api/public/manifest.webmanifest?v={version}",
        "icon_192_url": f"/api/public/pwa/icon-192.png?v={version}",
        "icon_512_url": f"/api/public/pwa/icon-512.png?v={version}",
        "maskable_icon_url": f"/api/public/pwa/icon-maskable-512.png?v={version}",
        "apple_touch_icon_url": f"/api/public/pwa/apple-touch-icon.png?v={version}",
        "favicon_url": f"/api/public/pwa/favicon.ico?v={version}",
    }
