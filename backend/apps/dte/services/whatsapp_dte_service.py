from __future__ import annotations

from dataclasses import dataclass
import logging
import re
import time

import requests

from apps.dte.services.delivery_payloads import build_delivery_base_payload
from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import resolve_delivery_config

logger = logging.getLogger("apps.dte")
PHONE_RE = re.compile(r"^\d{8,15}$")
INVALID_PHONES = {"00000000", "000000000", "0000000000", "50300000000"}


def _normalize_phone(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _mask_phone(value: str | None) -> str:
    digits = _normalize_phone(value)
    if not digits:
        return "***"
    tail = digits[-4:] if len(digits) >= 4 else digits
    return f"***{tail}"


def _is_valid_phone(phone: str) -> bool:
    if not PHONE_RE.match(phone):
        return False
    if phone in INVALID_PHONES or set(phone) == {"0"}:
        return False
    return True


@dataclass(frozen=True)
class WhatsAppDestinationResolution:
    raw_phone: str
    normalized_phone: str
    source: str
    rejected_reason: str
    is_valid: bool


def resolve_whatsapp_destination(
    record: DTERecord,
    *,
    to_phone: str | None = None,
    allow_default_fallback: bool | None = None,
) -> WhatsAppDestinationResolution:
    config = resolve_delivery_config()
    customer_phone = _normalize_phone(getattr(getattr(record.order, "customer", None), "telefono", ""))
    requested_raw = str(to_phone or "").strip()
    requested_phone = _normalize_phone(requested_raw)
    default_phone = _normalize_phone(config.whatsapp_default_phone)
    fallback_enabled = config.whatsapp_allow_default_fallback if allow_default_fallback is None else bool(allow_default_fallback)

    if requested_raw:
        if not requested_phone:
            return WhatsAppDestinationResolution(
                raw_phone=requested_raw,
                normalized_phone="",
                source="client_phone",
                rejected_reason="Teléfono de cliente inválido para WhatsApp.",
                is_valid=False,
            )
        if not _is_valid_phone(requested_phone):
            return WhatsAppDestinationResolution(
                raw_phone=requested_raw,
                normalized_phone=requested_phone,
                source="client_phone",
                rejected_reason="Teléfono de cliente inválido para WhatsApp.",
                is_valid=False,
            )
        return WhatsAppDestinationResolution(
            raw_phone=requested_raw,
            normalized_phone=requested_phone,
            source="client_phone",
            rejected_reason="",
            is_valid=True,
        )

    if customer_phone and _is_valid_phone(customer_phone):
        return WhatsAppDestinationResolution(
            raw_phone=customer_phone,
            normalized_phone=customer_phone,
            source="client_phone",
            rejected_reason="",
            is_valid=True,
        )

    if fallback_enabled and default_phone and _is_valid_phone(default_phone):
        return WhatsAppDestinationResolution(
            raw_phone=default_phone,
            normalized_phone=default_phone,
            source="default_fallback",
            rejected_reason="",
            is_valid=True,
        )

    reason = "Cliente sin teléfono válido."
    if not fallback_enabled:
        reason = "Cliente sin teléfono válido y fallback por defecto deshabilitado."
    return WhatsAppDestinationResolution(
        raw_phone=requested_raw or customer_phone or default_phone,
        normalized_phone="",
        source="client_phone" if (requested_raw or customer_phone) else "default_fallback",
        rejected_reason=reason,
        is_valid=False,
    )


def validate_whatsapp_target(
    record: DTERecord,
    to_phone: str | None = None,
    *,
    allow_default_fallback: bool | None = None,
) -> tuple[bool, str, str]:
    resolved = resolve_whatsapp_destination(
        record,
        to_phone=to_phone,
        allow_default_fallback=allow_default_fallback,
    )
    return resolved.is_valid, resolved.rejected_reason, resolved.normalized_phone


def _safe_dte_for_whatsapp(record: DTERecord) -> dict:
    request_payload = record.request_payload or {}
    if not isinstance(request_payload, dict):
        return {}
    dte = request_payload.get("dte")
    if not isinstance(dte, dict):
        return {}
    receptor = dte.get("receptor") if isinstance(dte.get("receptor"), dict) else {}
    direccion = receptor.get("direccion") if isinstance(receptor.get("direccion"), dict) else {}
    safe_receptor = {
        **receptor,
        "direccion": {
            "departamento": str(direccion.get("departamento") or "").strip(),
            "municipio": str(direccion.get("municipio") or "").strip(),
            "complemento": str(direccion.get("complemento") or "").strip(),
        },
    }
    return {**dte, "receptor": safe_receptor}


def build_whatsapp_payload(record: DTERecord, destination: WhatsAppDestinationResolution) -> dict:
    base = build_delivery_base_payload(record)
    dte = _safe_dte_for_whatsapp(record) or (base.get("invoice_json") if isinstance(base.get("invoice_json"), dict) else {})
    response_payload = base.get("hacienda_response") if isinstance(base.get("hacienda_response"), dict) else {}
    tipo_dte = "01"
    doc_type = "CF"
    normalized = (record.dte_type or "").upper()
    if normalized.startswith("CCF"):
        tipo_dte, doc_type = "03", "CCF"
    elif normalized.startswith("SE"):
        tipo_dte, doc_type = "14", "SX"
    elif isinstance(dte.get("identificacion"), dict) and dte["identificacion"].get("tipoDte"):
        tipo_dte = str(dte["identificacion"]["tipoDte"])
    empresa_nombre = base.get("company_name") or resolve_delivery_config().whatsapp_company_name or "PicoPOS"
    resumen = dte.get("resumen") if isinstance(dte.get("resumen"), dict) else {}
    total = float(resumen.get("totalPagar") or base.get("total") or record.total_amount or 0)
    return {
        "num_receptor": destination.normalized_phone,
        "send_json": True,
        "dte": dte,
        "tipo_dte": tipo_dte,
        "doc_type": doc_type,
        "issued_id": base.get("issued_id"),
        "order_id": base.get("order_id"),
        "generation_code": base.get("generation_code"),
        "control_number": base.get("control_number"),
        "receiver_name": base.get("receiver_name"),
        "estado_mh": base.get("estado_mh"),
        "empresa_nombre": empresa_nombre,
        "total": total,
        "hacienda_response": response_payload,
        "sello_recibido": base.get("sello_recibido") or "",
        "fh_procesamiento": base.get("fh_procesamiento"),
        "descripcion_msg": f"DTE {record.control_number} estado {record.status}",
    }


def send_dte_whatsapp(record: DTERecord, to_phone: str | None = None) -> DteDeliveryAttempt:
    config = resolve_delivery_config()
    endpoint = config.whatsapp_url
    key = config.whatsapp_api_key

    attempt = DteDeliveryAttempt.objects.create(dte_record=record, delivery_type=DteDeliveryAttempt.TYPE_WA, status="PENDING", retries=0)
    provider_status = 0
    provider_body = {}
    error = ""
    destination = resolve_whatsapp_destination(record, to_phone=to_phone)

    if not destination.is_valid:
        attempt.status = "FAILED"
        attempt.provider_body = {
            "error": destination.rejected_reason,
            "provider_message": destination.rejected_reason,
            "to_phone": destination.normalized_phone or None,
            "destination_source": destination.source,
            "raw_phone_masked": _mask_phone(destination.raw_phone),
            "normalized_phone_masked": _mask_phone(destination.normalized_phone),
        }
        attempt.save(update_fields=["status", "provider_body", "retries"])
        logger.warning(
            "WHATSAPP_JOB_START job_id=%s destination_source=%s raw_phone=%s normalized_phone=%s error=%s",
            attempt.id,
            destination.source,
            _mask_phone(destination.raw_phone),
            _mask_phone(destination.normalized_phone),
            destination.rejected_reason,
        )
        return attempt

    payload = build_whatsapp_payload(record, destination)
    logger.info(
        "WHATSAPP_JOB_START job_id=%s destination_source=%s destination=%s endpoint=%s tipo_dte=%s gen=%s control=%s has_sello=%s has_pdf=%s has_json=%s",
        attempt.id,
        destination.source,
        _mask_phone(destination.normalized_phone),
        endpoint,
        payload.get("tipo_dte"),
        payload.get("generation_code"),
        payload.get("control_number"),
        bool(payload.get("sello_recibido")),
        True,
        bool(payload.get("send_json")),
    )

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "WHATSAPP_DTE_API_BASE missing"
            break
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers={"X-API-Key": key, "Content-Type": "application/json"},
                timeout=8,
            )
            provider_status = response.status_code
            provider_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text[:3000]}
            logger.info(
                "WHATSAPP_PROVIDER_RESPONSE job_id=%s delivery_type=%s destination=%s status=%s body=%s",
                attempt.id,
                "json_bundle",
                _mask_phone(destination.normalized_phone),
                response.status_code,
                str(provider_body)[:800],
            )
            if 200 <= response.status_code < 300:
                provider_status_text = str((provider_body or {}).get("status") or "").strip().lower()
                is_queued = bool((provider_body or {}).get("queued")) or provider_status_text == "queued"
                attempt.status = "QUEUED" if is_queued else "SENT"
                break
            error = f"http_{response.status_code}"
            logger.warning(
                "WHATSAPP_PROVIDER_ERROR job_id=%s destination=%s status=%s provider_message=%s",
                attempt.id,
                _mask_phone(destination.normalized_phone),
                response.status_code,
                str((provider_body or {}).get("message") or (provider_body or {}).get("detail") or "")[:600],
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            logger.warning(
                "WHATSAPP_PROVIDER_EXCEPTION job_id=%s destination=%s error=%s",
                attempt.id,
                _mask_phone(destination.normalized_phone),
                error,
            )
        time.sleep(1)

    if attempt.status not in {"SENT", "QUEUED"}:
        attempt.status = "FAILED"
    attempt.provider_status = provider_status or None
    provider_status_text = str((provider_body or {}).get("status") or "").strip().lower()
    queued = attempt.status == "QUEUED" or bool((provider_body or {}).get("queued")) or provider_status_text == "queued"
    provider_message = str(
        (provider_body or {}).get("message")
        or (provider_body or {}).get("detail")
        or ("Job encolado para envío por WhatsApp" if queued else error)
        or ""
    ).strip()
    attempt.provider_body = {
        **(provider_body or {}),
        "error": error or None,
        "provider_message": provider_message or None,
        "request_payload": payload,
        "to_phone": destination.normalized_phone,
        "destination_source": destination.source,
        "raw_phone_masked": _mask_phone(destination.raw_phone),
        "normalized_phone_masked": _mask_phone(destination.normalized_phone),
        "endpoint": endpoint,
        "queued": queued,
        "job_id": (provider_body or {}).get("job_id"),
    }
    attempt.save(update_fields=["status", "provider_status", "provider_body", "retries"])
    logger.info(
        "WHATSAPP_JOB_FINISH job_id=%s status=%s destination_source=%s destination=%s provider_status=%s error=%s",
        attempt.id,
        attempt.status,
        destination.source,
        _mask_phone(destination.normalized_phone),
        provider_status,
        error,
    )
    return attempt
