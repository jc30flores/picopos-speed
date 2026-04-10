from __future__ import annotations

import logging
import time

import requests

from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import resolve_delivery_config

logger = logging.getLogger("apps.dte")


def build_whatsapp_payload(record: DTERecord, to_phone: str | None = None) -> dict:
    default_phone = resolve_delivery_config().whatsapp_default_phone
    return {
        "order_id": record.order_id,
        "dte_id": record.id,
        "to": to_phone or default_phone,
        "message": f"DTE {record.control_number} estado {record.status}",
    }


def send_dte_whatsapp(record: DTERecord, to_phone: str | None = None) -> DteDeliveryAttempt:
    config = resolve_delivery_config()
    endpoint = config.whatsapp_url
    key = config.whatsapp_api_key
    payload = build_whatsapp_payload(record, to_phone=to_phone)

    attempt = DteDeliveryAttempt.objects.create(dte_record=record, delivery_type=DteDeliveryAttempt.TYPE_WA, status="PENDING", retries=0)
    provider_status = 0
    provider_body = {}
    error = ""

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "WHATSAPP_DTE_API_BASE missing"
            break
        try:
            response = requests.post(endpoint, json=payload, headers={"X-API-Key": key}, timeout=8)
            provider_status = response.status_code
            provider_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text[:500]}
            if 200 <= response.status_code < 300:
                attempt.status = "SENT"
                break
            error = f"http_{response.status_code}"
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
        time.sleep(1)

    if attempt.status != "SENT":
        attempt.status = "FAILED"
    attempt.provider_status = provider_status or None
    attempt.provider_body = {**(provider_body or {}), "error": error or None}
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
