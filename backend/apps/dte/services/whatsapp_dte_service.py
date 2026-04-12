from __future__ import annotations

import logging
import re
import time

import requests

from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import resolve_delivery_config

logger = logging.getLogger("apps.dte")
PHONE_RE = re.compile(r"^\d{8,15}$")
INVALID_PHONES = {"00000000", "000000000", "0000000000", "50300000000"}


def _normalize_phone(value: str | None) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits


def validate_whatsapp_target(record: DTERecord, to_phone: str | None = None) -> tuple[bool, str, str]:
    default_phone = resolve_delivery_config().whatsapp_default_phone
    customer_phone = _normalize_phone(getattr(getattr(record.order, "customer", None), "telefono", ""))
    phone = _normalize_phone(to_phone) or customer_phone or _normalize_phone(default_phone)
    if not phone:
        return False, "Cliente sin teléfono", ""
    if not PHONE_RE.match(phone):
        return False, "Teléfono inválido para WhatsApp", phone
    if phone in INVALID_PHONES or set(phone) == {"0"}:
        return False, "Teléfono inválido para WhatsApp", phone
    return True, "", phone


def build_whatsapp_payload(record: DTERecord, to_phone: str | None = None) -> dict:
    _, _, target = validate_whatsapp_target(record, to_phone=to_phone)
    request_payload = record.request_payload or {}
    dte = request_payload.get("dte") if isinstance(request_payload, dict) and isinstance(request_payload.get("dte"), dict) else {}
    response_payload = record.response_payload or {}
    tipo_dte = "01"
    doc_type = "CF"
    normalized = (record.dte_type or "").upper()
    if normalized.startswith("CCF"):
        tipo_dte, doc_type = "03", "CCF"
    elif normalized.startswith("SE"):
        tipo_dte, doc_type = "14", "SX"
    elif isinstance(dte.get("identificacion"), dict) and dte["identificacion"].get("tipoDte"):
        tipo_dte = str(dte["identificacion"]["tipoDte"])
    empresa_nombre = (
        (dte.get("emisor") or {}).get("nombreComercial")
        or (dte.get("emisor") or {}).get("nombre")
        or resolve_delivery_config().whatsapp_company_name
        or "PicoPOS"
    )
    resumen = dte.get("resumen") if isinstance(dte.get("resumen"), dict) else {}
    total = float(resumen.get("totalPagar") or record.total_amount or 0)
    return {
        "num_receptor": target,
        "send_json": True,
        "dte": dte,
        "tipo_dte": tipo_dte,
        "doc_type": doc_type,
        "empresa_nombre": empresa_nombre,
        "total": total,
        "hacienda_response": response_payload,
        "sello_recibido": record.sello_recibido or record.sello_recepcion or response_payload.get("sello_recibido") or "",
        "fh_procesamiento": (
            response_payload.get("fhProcesamiento")
            or response_payload.get("fh_procesamiento")
            or (record.recibido_at.isoformat() if record.recibido_at else None)
        ),
        "descripcion_msg": f"DTE {record.control_number} estado {record.status}",
    }


def send_dte_whatsapp(record: DTERecord, to_phone: str | None = None) -> DteDeliveryAttempt:
    config = resolve_delivery_config()
    endpoint = config.whatsapp_url
    key = config.whatsapp_api_key
    payload = {}

    attempt = DteDeliveryAttempt.objects.create(dte_record=record, delivery_type=DteDeliveryAttempt.TYPE_WA, status="PENDING", retries=0)
    provider_status = 0
    provider_body = {}
    error = ""
    ok_target, target_error, target_phone = validate_whatsapp_target(record, to_phone=to_phone)
    if not ok_target:
        attempt.status = "FAILED"
        attempt.provider_body = {"error": target_error, "provider_message": target_error, "to_phone": target_phone or None}
        attempt.save(update_fields=["status", "provider_body", "retries"])
        logger.info(
            "[DTE WA] SEND order=%s status=%s provider_status=%s endpoint=%s has_key=%s error=%s to_phone=%s",
            record.order_id,
            attempt.status,
            None,
            endpoint,
            bool(key),
            target_error,
            target_phone or None,
        )
        return attempt

    payload = build_whatsapp_payload(record, to_phone=target_phone)
    logger.info(
        "[DTE WA] payload_summary order=%s endpoint=%s num_receptor=%s tipo_dte=%s doc_type=%s has_dte=%s send_json=%s",
        record.order_id,
        endpoint,
        payload.get("num_receptor"),
        payload.get("tipo_dte"),
        payload.get("doc_type"),
        isinstance(payload.get("dte"), dict) and bool(payload.get("dte")),
        payload.get("send_json"),
    )

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "WHATSAPP_DTE_API_BASE missing"
            break
        try:
            response = requests.post(endpoint, json=payload, headers={"X-API-Key": key, "Content-Type": "application/json"}, timeout=8)
            provider_status = response.status_code
            provider_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text[:3000]}
            if 200 <= response.status_code < 300:
                provider_status_text = str((provider_body or {}).get("status") or "").strip().lower()
                is_queued = bool((provider_body or {}).get("queued")) or provider_status_text == "queued"
                attempt.status = "QUEUED" if is_queued else "SENT"
                logger.info("[DTE WA] provider_success order=%s status=%s body=%s", record.order_id, response.status_code, (response.text or "")[:3000])
                break
            error = f"http_{response.status_code}"
            logger.warning(
                "[DTE WA] provider_error order=%s endpoint=%s status=%s payload=%s provider_body=%s",
                record.order_id,
                endpoint,
                response.status_code,
                payload,
                (response.text or "")[:3000],
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        time.sleep(1)

    if attempt.status not in {"SENT", "QUEUED"}:
        attempt.status = "FAILED"
    attempt.provider_status = provider_status or None
    provider_status_text = str((provider_body or {}).get("status") or "").strip().lower()
    queued = attempt.status == "QUEUED" or bool((provider_body or {}).get("queued")) or provider_status_text == "queued"
    provider_message = str((provider_body or {}).get("message") or (provider_body or {}).get("detail") or ("Job encolado para envío por WhatsApp" if queued else error) or "").strip()
    attempt.provider_body = {
        **(provider_body or {}),
        "error": error or None,
        "provider_message": provider_message or None,
        "request_payload": payload,
        "to_phone": target_phone,
        "endpoint": endpoint,
        "queued": queued,
        "job_id": (provider_body or {}).get("job_id"),
    }
    attempt.save(update_fields=["status", "provider_status", "provider_body", "retries"])
    logger.info(
        "[DTE WA] SEND order=%s status=%s provider_status=%s endpoint=%s has_key=%s error=%s",
        record.order_id,
        attempt.status,
        provider_status,
        endpoint,
        bool(key),
        error,
    )
    return attempt
