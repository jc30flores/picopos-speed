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
    raw, _ = resolve_ambiente_with_source()
    normalized = normalize_ambiente(raw)
    requires_prod = str(os.environ.get("DTE_REQUIRE_AMBIENTE_01", "")).strip().lower() in {"1", "true", "yes"}
    if requires_prod:
        return "01"
    return normalized


def resolve_ambiente_with_source() -> tuple[str, str]:
    if os.environ.get("DTE_AMBIENTE"):
        return os.environ["DTE_AMBIENTE"], "DTE_AMBIENTE"
    if os.environ.get("MH_AMBIENTE"):
        return os.environ["MH_AMBIENTE"], "MH_AMBIENTE"
    if os.environ.get("HACIENDA_AMBIENTE"):
        return os.environ["HACIENDA_AMBIENTE"], "HACIENDA_AMBIENTE"
    return "00", "default"
