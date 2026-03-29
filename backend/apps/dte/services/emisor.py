from __future__ import annotations

import os
import re
from typing import Any

from django.conf import settings
from rest_framework.exceptions import ValidationError

from apps.dte.models import DTEBranchConfig


def _digits(value: str | None) -> str:
    return re.sub(r"[^0-9]", "", value or "")


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, os.environ.get(name, default)) or "").strip()


def normalize_nit(value: str | None) -> str:
    digits = _digits(value)
    if len(digits) != 14:
        raise ValidationError(f"NIT emisor inválido: se esperaban 14 dígitos y se recibió '{value or ''}'.")
    return digits


def get_emisor_nit(branch) -> str:
    cfg = DTEBranchConfig.objects.filter(branch=branch, is_active=True).first() if branch else None
    cfg_nit = _digits(getattr(cfg, "emisor_nit", ""))
    if cfg_nit:
        return normalize_nit(cfg_nit)
    return normalize_nit(_setting("DTE_EMISOR_NIT"))


def get_emisor_config(branch) -> dict[str, Any]:
    cfg = DTEBranchConfig.objects.filter(branch=branch, is_active=True).first() if branch else None
    if cfg:
        return {
            "nit": get_emisor_nit(branch),
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
    return {
        "nit": get_emisor_nit(branch),
        "nrc": _setting("DTE_EMISOR_NRC"),
        "nombre": _setting("DTE_EMISOR_NOMBRE") or _setting("DTE_NOMBRE_COMERCIAL") or "Pico de Gallo",
        "nombreComercial": _setting("DTE_EMISOR_NOMBRE_COMERCIAL") or _setting("DTE_NOMBRE_COMERCIAL") or "Pico de Gallo",
        "codActividad": _setting("DTE_EMISOR_COD_ACTIVIDAD"),
        "descActividad": _setting("DTE_EMISOR_DESC_ACTIVIDAD"),
        "tipoEstablecimiento": _setting("DTE_EMISOR_TIPO_ESTABLECIMIENTO"),
        "codEstableMH": _setting("DTE_EMISOR_COD_ESTABLE_MH", "M001"),
        "codEstable": _setting("DTE_EMISOR_COD_ESTABLE", "M001"),
        "codPuntoVentaMH": _setting("DTE_EMISOR_COD_PUNTO_VENTA_MH", "P001"),
        "codPuntoVenta": _setting("DTE_EMISOR_COD_PUNTO_VENTA", "P001"),
        "departamento": _setting("DTE_EMISOR_DEPARTAMENTO"),
        "municipio": _setting("DTE_EMISOR_MUNICIPIO"),
        "complemento": _setting("DTE_EMISOR_DIRECCION"),
        "telefono": _setting("DTE_EMISOR_TELEFONO"),
        "correo": _setting("DTE_EMISOR_CORREO"),
    }


def payload_emisor_nit(payload: dict) -> str:
    raw = _digits(((payload or {}).get("dte") or {}).get("emisor", {}).get("nit"))
    return raw if len(raw) == 14 else ""
