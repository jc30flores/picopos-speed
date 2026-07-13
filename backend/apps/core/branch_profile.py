from __future__ import annotations

import os
from typing import Any

from django.conf import settings

from apps.core.models import Branch
from apps.dte.models import DTEBranchConfig


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, os.environ.get(name, default)) or "").strip()


def get_current_branch_id() -> int | None:
    return (
        _safe_int(getattr(settings, "BRANCH_ID", None))
        or _safe_int(getattr(settings, "POS_BRANCH_ID", None))
        or _safe_int(getattr(settings, "DEFAULT_BRANCH_ID", None))
    )


def get_active_branch_id() -> int | None:
    return get_current_branch_id()


def get_branch_profile(branch_id: int | None) -> dict[str, str]:
    branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
    cfg = DTEBranchConfig.objects.filter(branch=branch, is_active=True).first() if branch else None

    branch_name = ((branch.name if branch else "") or "Sucursal no configurada").strip()
    branch_code = ((branch.code if branch else "") or "N/A").strip()
    dte_address = (getattr(cfg, "direccion_complemento", "") or "").strip()
    env_address = _setting("DTE_DIRECCION_COMPLEMENTO") or _setting("DTE_EMISOR_DIRECCION")
    branch_address = (getattr(branch, "address", "") or "").strip()
    direccion_complemento = dte_address or env_address or branch_address or "(Dirección no configurada)"

    telefono = ((getattr(cfg, "telefono", "") if cfg else "") or _setting("DTE_EMISOR_TELEFONO")).strip()
    correo = ((getattr(cfg, "correo", "") if cfg else "") or _setting("DTE_EMISOR_CORREO")).strip()
    emisor_nombre = (
        (getattr(cfg, "emisor_nombre_comercial", "") if cfg else "")
        or (getattr(cfg, "emisor_nombre", "") if cfg else "")
        or _setting("DTE_EMISOR_NOMBRE_COMERCIAL")
        or _setting("DTE_EMISOR_NOMBRE")
        or _setting("DTE_NOMBRE_COMERCIAL")
        or "GastroPOSV"
    ).strip()

    return {
        "branch_id": str(getattr(branch, "id", "") or ""),
        "branch_name": branch_name,
        "branch_code": branch_code,
        "emisor_nombre": emisor_nombre,
        "direccion_complemento": direccion_complemento,
        "telefono": telefono,
        "correo": correo,
    }
