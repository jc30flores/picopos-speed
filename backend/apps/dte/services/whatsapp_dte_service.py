from __future__ import annotations

import logging
import re
import time

import requests

from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import resolve_delivery_config

logger = logging.getLogger("apps.dte")
PHONE_RE = re.compile(r"^\d{8,15}$")


def _normalize_phone(value: str | None) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits


def validate_whatsapp_target(record: DTERecord, to_phone: str | None = None) -> tuple[bool, str, str]:
    default_phone = resolve_delivery_config().whatsapp_default_phone
    phone = _normalize_phone(to_phone or default_phone)
    if not phone:
        return False, "Cliente sin teléfono", ""
    if not PHONE_RE.match(phone):
        return False, "Teléfono inválido para WhatsApp", phone
    return True, "", phone


def build_whatsapp_payload(record: DTERecord, to_phone: str | None = None) -> dict:
    _, _, target = validate_whatsapp_target(record, to_phone=to_phone)
    return {
        "order_id": record.order_id,
        "dte_id": record.id,
        "to": target,
        "message": f"DTE {record.control_number} estado {record.status}",
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

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "WHATSAPP_DTE_API_BASE missing"
            break
        try:
            response = requests.post(endpoint, json=payload, headers={"X-API-Key": key}, timeout=8)
            provider_status = response.status_code
            provider_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text[:3000]}
            if 200 <= response.status_code < 300:
                attempt.status = "SENT"
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

    if attempt.status != "SENT":
        attempt.status = "FAILED"
    attempt.provider_status = provider_status or None
    provider_message = str((provider_body or {}).get("message") or (provider_body or {}).get("detail") or error or "").strip()
    attempt.provider_body = {
        **(provider_body or {}),
        "error": error or None,
        "provider_message": provider_message or None,
        "request_payload": payload,
        "to_phone": target_phone,
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
