from __future__ import annotations

from apps.dte.models import DTERecord


def normalize_status(response: dict) -> str:
    raw = str(response.get("status", "")).upper()
    ok = bool(response.get("ok"))
    if ok and raw in {"ACEPTADO", "ACCEPTED", "SENT"}:
        return DTERecord.STATUS_ACCEPTED
    if raw in {"RECHAZADO", "REJECTED"}:
        return DTERecord.STATUS_REJECTED
    if raw in {"INVALIDADO"}:
        return DTERecord.STATUS_INVALIDATED
    return DTERecord.STATUS_PENDING


def interpret_response(response: dict) -> dict:
    return {
        "status": normalize_status(response),
        "hacienda_state": str(response.get("state") or response.get("status") or ""),
        "sello_recepcion": response.get("selloRecibido") or response.get("selloRecepcion") or response.get("sello") or "",
        "hacienda_uuid": response.get("uuid") or response.get("hacienda_uuid") or "",
        "error_message": str(response.get("error") or ""),
        "error_code": str(response.get("error_code") or ""),
    }
