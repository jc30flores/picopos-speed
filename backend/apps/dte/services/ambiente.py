from __future__ import annotations

import os


_ALIASES_TEST = {"00", "0", "test", "prueba", "testing", "cert", "certificacion", "dev"}
_ALIASES_PROD = {"01", "1", "prod", "produccion", "production"}


def normalize_ambiente(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in _ALIASES_TEST:
        return "00"
    if value in _ALIASES_PROD:
        return "01"
    raise ValueError(f"Valor de ambiente no reconocido: {raw}")


def resolve_ambiente_from_env() -> str:
    raw = os.environ.get("DTE_AMBIENTE") or os.environ.get("MH_AMBIENTE") or os.environ.get("HACIENDA_AMBIENTE") or "00"
    normalized = normalize_ambiente(raw)
    requires_prod = str(os.environ.get("DTE_REQUIRE_AMBIENTE_01", "")).strip().lower() in {"1", "true", "yes"}
    if requires_prod:
        return "01"
    return normalized
