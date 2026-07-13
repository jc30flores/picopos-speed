from __future__ import annotations

import os
from datetime import date, datetime
import logging

from apps.dte.models import DTERecord

logger = logging.getLogger("apps.dte")


def _company_name_from_env() -> str:
    return (
        str(os.environ.get("COMPANY_NAME") or "").strip()
        or str(os.environ.get("DTE_NOMBRE_COMERCIAL") or "").strip()
        or "GastroPOSV"
    )


def _extract_dte_json(record: DTERecord) -> dict:
    request_payload = record.request_payload or {}
    if isinstance(request_payload, dict) and isinstance(request_payload.get("dte"), dict):
        return request_payload.get("dte") or {}
    if isinstance(request_payload, dict):
        return request_payload
    return {}


def _extract_respuesta_hacienda(response_payload: dict, dte_json: dict) -> tuple[dict, str]:
    if isinstance(response_payload.get("respuesta_hacienda"), dict):
        base = dict(response_payload.get("respuesta_hacienda") or {})
        source = "response_payload.respuesta_hacienda"
    elif isinstance(dte_json.get("respuesta_hacienda"), dict):
        base = dict(dte_json.get("respuesta_hacienda") or {})
        source = "dte.respuesta_hacienda"
    else:
        base = {}
        source = ""
    for key in ("selloRecibido", "sello_recibido", "fhProcesamiento", "fh_procesamiento"):
        if key not in base and response_payload.get(key) not in (None, ""):
            base[key] = response_payload.get(key)
            source = source or "response_payload"
    return base, source


def _safe_iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _extract_sello(record: DTERecord, response_payload: dict, dte_json: dict) -> tuple[str, str]:
    candidates = [
        ("dte_record.sello_recibido", str(record.sello_recibido or "").strip()),
        ("dte_record.sello_recepcion", str(record.sello_recepcion or "").strip()),
        ("response_payload.sello_recibido", str(response_payload.get("sello_recibido") or "").strip()),
        ("response_payload.selloRecepcion", str(response_payload.get("selloRecepcion") or "").strip()),
        (
            "response_payload.respuesta_hacienda.selloRecibido",
            str((response_payload.get("respuesta_hacienda") or {}).get("selloRecibido") or "").strip(),
        ),
        (
            "dte.identificacion.selloRecibido",
            str((dte_json.get("identificacion") or {}).get("selloRecibido") or "").strip(),
        ),
    ]
    for source, value in candidates:
        if value:
            return value, source
    return "", ""


def _extract_fh_procesamiento(record: DTERecord, response_payload: dict, dte_json: dict) -> tuple[str | None, str]:
    candidates = [
        ("response_payload.fhProcesamiento", _safe_iso(response_payload.get("fhProcesamiento"))),
        ("response_payload.fh_procesamiento", _safe_iso(response_payload.get("fh_procesamiento"))),
        (
            "response_payload.respuesta_hacienda.fhProcesamiento",
            _safe_iso((response_payload.get("respuesta_hacienda") or {}).get("fhProcesamiento")),
        ),
        (
            "response_payload.respuesta_hacienda.fh_procesamiento",
            _safe_iso((response_payload.get("respuesta_hacienda") or {}).get("fh_procesamiento")),
        ),
        ("dte.identificacion.fhProcesamiento", _safe_iso((dte_json.get("identificacion") or {}).get("fhProcesamiento"))),
        ("dte_record.hacienda_processed_at", _safe_iso(record.hacienda_processed_at)),
        ("dte_record.recibido_at", _safe_iso(record.recibido_at)),
    ]
    for source, value in candidates:
        if value:
            return value, source
    return None, ""


def build_delivery_base_payload(record: DTERecord) -> dict:
    dte_json = _extract_dte_json(record)
    response_payload = record.response_payload or {}
    respuesta_hacienda, respuesta_hacienda_source = _extract_respuesta_hacienda(response_payload, dte_json)
    identificacion = dte_json.get("identificacion") if isinstance(dte_json.get("identificacion"), dict) else {}
    receptor = dte_json.get("receptor") if isinstance(dte_json.get("receptor"), dict) else {}
    emisor = dte_json.get("emisor") if isinstance(dte_json.get("emisor"), dict) else {}
    customer = getattr(record.order, "customer", None)

    sello_recibido, sello_source = _extract_sello(record, response_payload, dte_json)
    fh_procesamiento, fh_source = _extract_fh_procesamiento(record, response_payload, dte_json)

    issue_date = (
        str(identificacion.get("fecEmi") or "").strip()
        or _safe_iso(record.issue_date)
        or ""
    )
    issue_time = str(identificacion.get("horEmi") or "").strip() or None
    total = float((dte_json.get("resumen") or {}).get("totalPagar") or record.total_amount or 0)
    company_name = (
        str(emisor.get("nombreComercial") or "").strip()
        or str(emisor.get("nombre") or "").strip()
        or _company_name_from_env()
    )
    receiver_name = (
        str(receptor.get("nombre") or "").strip()
        or str(getattr(customer, "nombre", "") or getattr(customer, "name", "") or "").strip()
        or str(record.receiver_name or "").strip()
    )
    receiver_email = str(getattr(customer, "correo", "") or getattr(customer, "email", "") or "").strip()
    receiver_phone = str(getattr(customer, "telefono", "") or "").strip()
    generation_code = str(record.generation_code or record.codigo_generacion or identificacion.get("codigoGeneracion") or "").strip()
    control_number = str(record.control_number or identificacion.get("numeroControl") or "").strip()
    tipo_dte = str(identificacion.get("tipoDte") or "").strip() or str(record.dte_type or "").strip()

    if not sello_recibido:
        logger.info(
            "DTE_DELIVERY_BASE_MISSING_SEAL dte_record_id=%s order_id=%s status=%s",
            record.id,
            record.order_id,
            record.status,
        )
    if not fh_procesamiento:
        logger.info(
            "DTE_DELIVERY_BASE_MISSING_FH_PROCESSING dte_record_id=%s order_id=%s status=%s",
            record.id,
            record.order_id,
            record.status,
        )
    invoice_json = {
        "dte": dte_json if isinstance(dte_json, dict) else {},
        "respuesta_hacienda": respuesta_hacienda if isinstance(respuesta_hacienda, dict) else {},
    }

    return {
        "issued_id": record.id,
        "order_id": record.order_id,
        "dte_type": record.dte_type,
        "tipo_dte": tipo_dte,
        "generation_code": generation_code,
        "control_number": control_number,
        "sello_recibido": sello_recibido,
        "sello_source": sello_source,
        "fh_source": fh_source,
        "issue_date": issue_date,
        "issue_time": issue_time,
        "fh_procesamiento": fh_procesamiento,
        "status": record.status,
        "estado_mh": str(record.estado_mh or record.hacienda_state or "").strip(),
        "receiver_name": receiver_name,
        "receiver_email": receiver_email,
        "receiver_phone": receiver_phone,
        "company_name": company_name,
        "invoice_json": invoice_json,
        "dte_json": dte_json,
        "respuesta_hacienda": respuesta_hacienda,
        "respuesta_hacienda_source": respuesta_hacienda_source,
        "hacienda_response": response_payload,
        "total": total,
        "attachments": {"pdf": True, "json": True},
    }
