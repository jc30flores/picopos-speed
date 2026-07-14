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
SITE_NAME = "GastroPOSV"


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


def customer_logo_file() -> tuple[TicketSettings | None, Path | None]:
    try:
        ticket_settings = TicketSettings.objects.filter(pk=1).first()
        if not ticket_settings or not ticket_settings.ticket_logo:
            return None, None
        path = Path(ticket_settings.ticket_logo.path)
        return (ticket_settings, path) if path.exists() else (ticket_settings, None)
    except (OSError, ValueError):
        logger.warning("pwa.ticket_logo_path_unavailable", exc_info=True)
        return None, None


def ticket_logo_path() -> Path | None:
    _ticket_settings, path = customer_logo_file()
    return path


def _logo_signature(ticket_settings: TicketSettings | None, path: Path | None) -> str:
    logo_name = ""
    logo_updated = ""
    logo_file_state = "missing"
    if ticket_settings and ticket_settings.ticket_logo:
        logo_name = ticket_settings.ticket_logo.name or ""
        logo_updated = ticket_settings.updated_at.isoformat() if ticket_settings.updated_at else ""
    if path:
        try:
            stat = path.stat()
            logo_file_state = f"{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            logo_file_state = "unreadable"
    return "|".join([logo_name, logo_updated, logo_file_state])


def branding_version(name: str, short: str, appearance: SystemAppearanceSettings, ticket_settings: TicketSettings | None, logo_path: Path | None) -> str:
    source = "|".join(
        [
            name,
            short,
            appearance.primary_color,
            appearance.updated_at.isoformat() if appearance.updated_at else "",
            _logo_signature(ticket_settings, logo_path),
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


def get_public_pwa_metadata() -> dict[str, str | bool | None]:
    appearance, _ = SystemAppearanceSettings.objects.get_or_create(pk=1)
    ticket_settings, logo_path = customer_logo_file()
    name = app_name()
    short = PROJECT_SHORT_NAME if name == PROJECT_APP_NAME else short_name(name)
    version = branding_version(name, short, appearance, ticket_settings, logo_path)
    theme_color = safe_hex(getattr(appearance, "color_primary", None) or appearance.primary_color)
    customer_logo_url = f"/api/public/pwa/customer-logo.png?v={version}" if logo_path else None
    return {
        "app_name": name,
        "short_name": short,
        "description": PWA_DESCRIPTION,
        "site_name": SITE_NAME,
        "theme_color": theme_color,
        "background_color": "#0B1020",
        "display": "standalone",
        "orientation": "any",
        "start_url": "/",
        "scope": "/",
        "version": version,
        "branding_version": version,
        "logo_version": version if logo_path else "",
        "has_customer_logo": bool(logo_path),
        "customer_logo_url": customer_logo_url,
        "ticket_logo_url": customer_logo_url,
        "manifest_url": f"/api/public/manifest.webmanifest?v={version}",
        "icon_192_url": f"/api/public/pwa/icon-192.png?v={version}",
        "icon_512_url": f"/api/public/pwa/icon-512.png?v={version}",
        "maskable_icon_url": f"/api/public/pwa/icon-maskable-512.png?v={version}",
        "apple_touch_icon_url": f"/api/public/pwa/apple-touch-icon.png?v={version}",
        "favicon_url": f"/api/public/pwa/favicon.ico?v={version}",
        "share_image_url": f"/api/public/pwa/share-image.png?v={version}",
    }
