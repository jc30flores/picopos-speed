from __future__ import annotations

from datetime import datetime


def _walk(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _first_value(payload: dict, keys: tuple[str, ...]) -> str:
    for node in _walk(payload):
        if not isinstance(node, dict):
            continue
        for key in keys:
            if key in node and node.get(key) not in (None, ""):
                return str(node.get(key))
    return ""


def _parse_datetime(raw: str) -> datetime | None:
    if not raw:
        return None
    value = raw.strip()
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def parse_hacienda_response(response: dict) -> dict:
    ok = bool(response.get("ok"))
    raw_status = str(response.get("status", "")).upper()
    if ok and raw_status in {"SENT", "ACEPTADO", "ACCEPTED"}:
        status = "aceptado"
    elif raw_status in {"REJECTED", "RECHAZADO"}:
        status = "rechazado"
    else:
        status = "pendiente"

    seal = _first_value(response, ("selloRecibido", "selloRecepcion", "sello"))
    uuid = _first_value(response, ("uuid", "hacienda_uuid", "codigoGeneracion"))
    firma = _first_value(response, ("firma",))
    estado_mh = _first_value(response, ("estado", "estadoMh", "state")) or raw_status
    recibido_at_raw = _first_value(response, ("fhRecibido", "recibidoAt", "recibido_at", "fechaRecibido"))
    return {
        "status": status,
        "hacienda_state": estado_mh,
        "estado_mh": estado_mh,
        "sello_recepcion": seal,
        "sello_recibido": seal,
        "firma": firma,
        "recibido_at": _parse_datetime(recibido_at_raw),
        "hacienda_uuid": uuid,
        "error": response.get("error", ""),
        "error_code": response.get("error_code", ""),
    }
