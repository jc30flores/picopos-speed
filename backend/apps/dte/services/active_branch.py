from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.core.models import Branch

logger = logging.getLogger("apps.dte")


def get_active_branch_code() -> str:
    code = str(getattr(settings, "ACTIVE_BRANCH_CODE", "") or "").strip()
    if code:
        return code

    branch_id = (
        getattr(settings, "BRANCH_ID", None)
        or getattr(settings, "POS_BRANCH_ID", None)
        or getattr(settings, "DEFAULT_BRANCH_ID", None)
    )
    if branch_id:
        branch = Branch.objects.filter(id=branch_id).first()
        if branch and branch.code:
            logger.warning("[DTE] ACTIVE_BRANCH_CODE no configurado; usando fallback por BRANCH_ID=%s -> %s", branch_id, branch.code)
            return branch.code

    raise ImproperlyConfigured(
        "ACTIVE_BRANCH_CODE no está configurado en .env y no fue posible resolver fallback por BRANCH_ID."
    )


def get_active_branch() -> Branch:
    code = get_active_branch_code()
    branch = Branch.objects.filter(code=code, is_active=True).first()
    if not branch:
        raise ImproperlyConfigured(
            f"ACTIVE_BRANCH_CODE='{code}' no coincide con una sucursal activa en core_branch."
        )
    logger.info("[DTE DEBUG] Emisor branch activo=%s (id=%s)", branch.code, branch.id)
    return branch
