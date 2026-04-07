from __future__ import annotations

import logging
import time

import requests
from django.conf import settings

from apps.dte.models import DTERecord, DteDeliveryAttempt

logger = logging.getLogger("apps.dte")


def build_email_payload(record: DTERecord, to_email: str | None = None) -> dict:
    return {
        "order_id": record.order_id,
        "dte_id": record.id,
        "to": to_email or getattr(record.order.customer, "correo", None) if record.order.customer_id else None,
        "subject": f"DTE {record.control_number}",
        "metadata": {"dte_type": record.dte_type, "status": record.status},
    }


def send_dte_email(record: DTERecord, to_email: str | None = None) -> DteDeliveryAttempt:
    base = ((getattr(settings, "DELIVER_EMAIL_API_BASE_URL", "") or "").strip() or (getattr(settings, "EMAIL_API_BASE_URL", "") or "").strip()).rstrip("/")
    key = (getattr(settings, "DELIVER_EMAIL_API_KEY", "") or "").strip() or (getattr(settings, "EMAIL_API_KEY", "") or "").strip()
    endpoint = f"{base}/send" if base else ""
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
    logger.info("[DTE EMAIL] SEND order=%s status=%s provider_status=%s error=%s", record.order_id, attempt.status, provider_status, error)
    return attempt
