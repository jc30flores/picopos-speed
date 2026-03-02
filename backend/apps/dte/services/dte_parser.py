from __future__ import annotations


def parse_hacienda_response(response: dict) -> dict:
    ok = bool(response.get("ok"))
    raw_status = str(response.get("status", "")).upper()
    if ok and raw_status in {"SENT", "ACEPTADO", "ACCEPTED"}:
        status = "aceptado"
    elif raw_status in {"REJECTED", "RECHAZADO"}:
        status = "rechazado"
    else:
        status = "pendiente"

    seal = response.get("selloRecibido") or response.get("selloRecepcion") or response.get("sello") or ""
    uuid = response.get("uuid") or response.get("hacienda_uuid") or ""
    return {
        "status": status,
        "hacienda_state": response.get("state") or raw_status,
        "sello_recepcion": seal,
        "hacienda_uuid": uuid,
        "error": response.get("error", ""),
        "error_code": response.get("error_code", ""),
    }
