from __future__ import annotations


def mask_value(value: str, keep: int = 3) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * (len(value) - keep)}{value[-keep:]}"


def redact_payload(payload: dict) -> dict:
    redacted = dict(payload or {})
    receptor = redacted.get("receptor") or {}
    if isinstance(receptor, dict):
        if receptor.get("nit"):
            receptor["nit"] = mask_value(str(receptor["nit"]))
        if receptor.get("telefono"):
            receptor["telefono"] = mask_value(str(receptor["telefono"]))
        if receptor.get("correo"):
            receptor["correo"] = mask_value(str(receptor["correo"]), keep=5)
        redacted["receptor"] = receptor
    return redacted
