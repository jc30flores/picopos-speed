from __future__ import annotations

import logging
import time
from typing import Any

import requests

from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import resolve_delivery_config

logger = logging.getLogger("apps.dte")


def build_email_payload(record: DTERecord, to_email: str | None = None) -> dict:
    dte_payload: dict[str, Any] = {}
    if isinstance(record.request_payload, dict):
        dte_payload = record.request_payload.get("dte") if isinstance(record.request_payload.get("dte"), dict) else record.request_payload
    identificacion = dte_payload.get("identificacion") if isinstance(dte_payload, dict) else {}
    numero_control = record.control_number or (identificacion.get("numeroControl") if isinstance(identificacion, dict) else None)
    codigo_generacion = record.generation_code or (identificacion.get("codigoGeneracion") if isinstance(identificacion, dict) else None)
    recipient = to_email or (getattr(record.order.customer, "correo", None) if record.order.customer_id else None)
    return {
        "order_id": record.order_id,
        "dte_id": record.id,
        "to": recipient,
        "email": recipient,
        "to_email": recipient,
        "subject": f"DTE {record.control_number}",
        "message": f"DTE {record.control_number}",
        "numero_control": numero_control,
        "codigo_generacion": codigo_generacion,
        "dte_type": record.dte_type,
        "dte_status": record.status,
        "invoice_json": dte_payload,
        "metadata": {"dte_type": record.dte_type, "status": record.status},
    }


def send_dte_email(record: DTERecord, to_email: str | None = None) -> DteDeliveryAttempt:
    config = resolve_delivery_config()
    endpoint = config.email_url
    key = config.email_api_key
    payload = build_email_payload(record, to_email=to_email)

    attempt = DteDeliveryAttempt.objects.create(dte_record=record, delivery_type=DteDeliveryAttempt.TYPE_EMAIL, status="PENDING", retries=0)
    provider_status = 0
    provider_body = {}
    error = ""

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "DELIVER_EMAIL_API_BASE_URL missing"
            break
        try:
            response = requests.post(endpoint, json=payload, headers={"X-API-Key": key}, timeout=8)
            provider_status = response.status_code
            provider_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text[:4000]}
            if 200 <= response.status_code < 300:
                attempt.status = "SENT"
                break
            error = f"http_{response.status_code}"
            logger.error(
                "[DTE EMAIL] provider_reject status=%s body=%s endpoint=%s order=%s",
                response.status_code,
                provider_body,
                endpoint,
                record.order_id,
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        time.sleep(1)

    if attempt.status != "SENT":
        attempt.status = "FAILED"
    attempt.provider_status = provider_status or None
    attempt.provider_body = {**(provider_body or {}), "error": error or None}
    attempt.save(update_fields=["status", "provider_status", "provider_body", "retries"])
    logger.info(
        "[DTE EMAIL] SEND order=%s status=%s provider_status=%s endpoint=%s has_key=%s error=%s",
        record.order_id,
        attempt.status,
        provider_status,
        endpoint,
        bool(key),
        error,
    )
    return attempt
