from __future__ import annotations

import logging
import re
import time

import requests

from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import INTERNAL_BILLING_EMAIL
from apps.dte.services.delivery_config import resolve_delivery_config

logger = logging.getLogger("apps.dte")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _resolve_email_target(record: DTERecord, to_email: str | None = None) -> str:
    explicit_email = str(to_email or "").strip()
    if explicit_email:
        return explicit_email
    if record.order.customer_id:
        return str(getattr(record.order.customer, "correo", "") or "").strip()
    return ""


def validate_delivery_email_target(record: DTERecord, to_email: str | None = None) -> tuple[bool, str, str]:
    email = _resolve_email_target(record, to_email=to_email)
    if not email:
        return False, "Cliente sin correo", ""
    if not EMAIL_RE.match(email):
        return False, "Correo de cliente inválido", email
    if email.lower() == INTERNAL_BILLING_EMAIL.lower():
        return False, "Correo interno no permitido para envío automático", email
    return True, "", email


def build_email_payload(record: DTERecord, to_email: str | None = None) -> dict:
    _, _, recipient = validate_delivery_email_target(record, to_email=to_email)
    invoice_json = {
        "order_id": record.order_id,
        "dte_id": record.id,
        "dte_type": record.dte_type,
        "status": record.status,
        "numero_control": record.control_number,
        "codigo_generacion": record.generation_code or record.codigo_generacion,
        "sello_recibido": record.sello_recibido or record.sello_recepcion,
        "hacienda_response": record.response_payload or {},
        "dte_payload": record.request_payload or {},
    }
    return {
        "to_email": recipient,
        "subject": f"DTE {record.control_number}",
        "body_text": f"Adjuntamos comprobante DTE {record.control_number}.",
        "invoice_json": invoice_json,
        "flags": {"source": "picopos", "channel": "email_dte"},
        "metadata": {"dte_type": record.dte_type, "status": record.status},
    }


def _parse_provider_body(response) -> tuple[dict, str]:
    content_type = (response.headers.get("content-type", "") or "").lower()
    raw_text = (response.text or "")[:3000]
    if "application/json" in content_type:
        try:
            return response.json(), raw_text
        except ValueError:
            return {"raw": raw_text}, raw_text
    return {"raw": raw_text}, raw_text


def _extract_provider_message(provider_body: dict, fallback: str) -> str:
    if not isinstance(provider_body, dict):
        return fallback
    for key in ("message", "detail", "error_description", "error"):
        value = provider_body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    errors = provider_body.get("errors")
    if isinstance(errors, dict):
        flat = []
        for field, msgs in errors.items():
            if isinstance(msgs, list):
                flat.append(f"{field}: {', '.join(str(m) for m in msgs)}")
            elif msgs:
                flat.append(f"{field}: {msgs}")
        if flat:
            return " | ".join(flat)
    return fallback


def send_dte_email(record: DTERecord, to_email: str | None = None) -> DteDeliveryAttempt:
    config = resolve_delivery_config()
    endpoint = config.email_url
    key = config.email_api_key
    payload = {}

    attempt = DteDeliveryAttempt.objects.create(dte_record=record, delivery_type=DteDeliveryAttempt.TYPE_EMAIL, status="PENDING", retries=0)
    provider_status = 0
    provider_body = {}
    error = ""
    ok_target, target_error, target_email = validate_delivery_email_target(record, to_email=to_email)
    if not ok_target:
        attempt.status = "FAILED"
        attempt.provider_body = {"error": target_error, "provider_message": target_error, "to_email": target_email or None}
        attempt.save(update_fields=["status", "provider_body", "retries"])
        logger.info(
            "[DTE EMAIL] SEND order=%s status=%s provider_status=%s endpoint=%s has_key=%s error=%s to_email=%s",
            record.order_id,
            attempt.status,
            None,
            endpoint,
            bool(key),
            target_error,
            target_email or None,
        )
        return attempt

    payload = build_email_payload(record, to_email=target_email)

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "DELIVER_EMAIL_API_BASE_URL missing"
            break
        try:
            response = requests.post(endpoint, json=payload, headers={"X-API-Key": key}, timeout=8)
            provider_status = response.status_code
            provider_body, raw_body = _parse_provider_body(response)
            if 200 <= response.status_code < 300:
                attempt.status = "SENT"
                break
            error = f"http_{response.status_code}"
            if response.status_code == 422:
                logger.warning(
                    "[DTE EMAIL] provider_422 order=%s endpoint=%s payload=%s provider_body=%s",
                    record.order_id,
                    endpoint,
                    payload,
                    raw_body or provider_body,
                )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        time.sleep(1)

    if attempt.status != "SENT":
        attempt.status = "FAILED"
    provider_message = _extract_provider_message(provider_body, error or "No se pudo enviar correo")
    attempt.provider_status = provider_status or None
    attempt.provider_body = {
        **(provider_body or {}),
        "error": error or None,
        "provider_message": provider_message,
        "request_payload": payload,
        "to_email": target_email,
    }
    attempt.save(update_fields=["status", "provider_status", "provider_body", "retries"])
    logger.info(
        "[DTE EMAIL] SEND order=%s status=%s provider_status=%s endpoint=%s has_key=%s error=%s provider_message=%s to_email=%s",
        record.order_id,
        attempt.status,
        provider_status,
        endpoint,
        bool(key),
        error,
        provider_message,
        target_email,
    )
    return attempt
