from __future__ import annotations

import logging
from pathlib import Path

from apps.core.models import TicketSettings

logger = logging.getLogger(__name__)


def get_ticket_settings() -> TicketSettings:
    settings, _ = TicketSettings.objects.get_or_create(pk=1)
    return settings


def get_ticket_logo_path() -> str | None:
    settings = TicketSettings.objects.filter(pk=1).first()
    if not settings or not settings.ticket_logo:
        return None
    try:
        path = Path(settings.ticket_logo.path)
    except (NotImplementedError, ValueError):
        logger.warning("ticket_settings.logo_path_unavailable id=%s", settings.pk)
        return None
    return str(path) if path.exists() else None
