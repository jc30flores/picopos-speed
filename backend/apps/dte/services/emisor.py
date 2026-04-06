from __future__ import annotations

import logging
import os
import re
from typing import Any

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.dte.models import DTEBranchConfig
from apps.dte.services.active_branch import get_active_branch

logger = logging.getLogger("apps.dte")


def _digits(value: str | None) -> str:
    return re.sub(r"[^0-9]", "", value or "")


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, os.environ.get(name, default)) or "").strip()


def _is_valid_nit(value: str | None) -> bool:
    return len(_digits(value)) == 14


def _get_valid_branch_config(branch) -> DTEBranchConfig | None:
    if not branch:
        return None
    configs = DTEBranchConfig.objects.filter(branch_id=branch.id, is_active=True).order_by("-updated_at", "-id")
    for cfg in configs:
        if _is_valid_nit(cfg.emisor_nit):
            return cfg
    return None


def normalize_nit(value: str | None, *, source: str = "desconocido") -> str:
    digits = _digits(value)
    if len(digits) != 14:
        raise ValidationError(
            f"NIT emisor inválido ({source}): se esperaban 14 dígitos y se recibió '{value or ''}'."
        )
    return digits


def get_emisor_nit(branch=None) -> str:
    branch_obj = get_active_branch()
    cfg = _get_valid_branch_config(branch_obj)
    cfg_nit = _digits(getattr(cfg, "emisor_nit", ""))
    if cfg_nit:
        logger.info("dte.emisor.nit source=DTEBranchConfig branch_id=%s", getattr(branch_obj, "id", None))
        return normalize_nit(cfg_nit, source="DTEBranchConfig.emisor_nit")
    branch_nit = _digits(getattr(branch_obj, "nit", "")) if branch_obj else ""
    if branch_nit:
        logger.info("dte.emisor.nit source=Branch.nit branch_id=%s", getattr(branch_obj, "id", None))
        return normalize_nit(branch_nit, source="Branch.nit")
    logger.info("dte.emisor.nit source=ENV branch_id=%s", getattr(branch_obj, "id", None))
    return normalize_nit(_setting("DTE_EMISOR_NIT"), source="DTE_EMISOR_NIT")


def get_emisor_config(branch=None) -> dict[str, Any]:
    branch_obj = get_active_branch()
    cfg = _get_valid_branch_config(branch_obj)
    if cfg:
        logger.info("dte.emisor.config source=DTEBranchConfig branch_id=%s", getattr(branch_obj, "id", None))
        return {
            "nit": get_emisor_nit(branch_obj),
            "nrc": (cfg.emisor_nrc or "").strip(),
            "nombre": (cfg.emisor_nombre or "").strip(),
            "nombreComercial": (cfg.emisor_nombre_comercial or "").strip(),
            "codActividad": (cfg.cod_actividad or "").strip(),
            "descActividad": (cfg.desc_actividad or "").strip(),
            "tipoEstablecimiento": (cfg.tipo_establecimiento or "").strip(),
            "codEstableMH": (cfg.cod_estable_mh or "").strip(),
            "codEstable": (cfg.cod_estable or "").strip(),
            "codPuntoVentaMH": (cfg.cod_punto_venta_mh or "").strip(),
            "codPuntoVenta": (cfg.cod_punto_venta or "").strip(),
            "departamento": (cfg.direccion_departamento or "").strip(),
            "municipio": (cfg.direccion_municipio or "").strip(),
            "complemento": (cfg.direccion_complemento or "").strip(),
            "telefono": (cfg.telefono or "").strip(),
            "correo": (cfg.correo or "").strip(),
        }
    logger.info("dte.emisor.config source=ENV branch_id=%s", getattr(branch_obj, "id", None))
    return {
        "nit": get_emisor_nit(branch_obj),
        "nrc": _setting("DTE_EMISOR_NRC"),
        "nombre": _setting("DTE_EMISOR_NOMBRE") or _setting("DTE_NOMBRE_COMERCIAL") or "Pico de Gallo",
        "nombreComercial": _setting("DTE_EMISOR_NOMBRE_COMERCIAL") or _setting("DTE_NOMBRE_COMERCIAL") or "Pico de Gallo",
        "codActividad": _setting("DTE_EMISOR_COD_ACTIVIDAD"),
        "descActividad": _setting("DTE_EMISOR_DESC_ACTIVIDAD"),
        "tipoEstablecimiento": _setting("DTE_EMISOR_TIPO_ESTABLECIMIENTO"),
        "codEstableMH": _setting("DTE_EMISOR_COD_ESTABLE_MH", "X001"),
        "codEstable": _setting("DTE_EMISOR_COD_ESTABLE", "X001"),
        "codPuntoVentaMH": _setting("DTE_EMISOR_COD_PUNTO_VENTA_MH", "X001"),
        "codPuntoVenta": _setting("DTE_EMISOR_COD_PUNTO_VENTA", "X001"),
        "departamento": _setting("DTE_EMISOR_DEPARTAMENTO"),
        "municipio": _setting("DTE_EMISOR_MUNICIPIO"),
        "complemento": _setting("DTE_EMISOR_DIRECCION"),
        "telefono": _setting("DTE_EMISOR_TELEFONO"),
        "correo": _setting("DTE_EMISOR_CORREO"),
    }


def payload_emisor_nit(payload: dict) -> str:
    raw = _digits(((payload or {}).get("dte") or {}).get("emisor", {}).get("nit"))
    return raw if len(raw) == 14 else ""
