from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.dte.client import DTEClient
from apps.dte.models import DTEOutbox, DTERecord
from apps.orders.models import OrderInvoice

logger = logging.getLogger(__name__)


def classify_outbox_status(status_code: int, body: dict, error_type: str = "") -> str:
    estado = str((body or {}).get("estado") or "").upper()
    rh = (body or {}).get("respuesta_hacienda") or {}
    rh_estado = str((rh or {}).get("estado") or "").upper()

    if estado == "ACEPTADO" or rh_estado in {"ACEPTADO", "PROCESADO", "RECIBIDO"}:
        return DTEOutbox.STATUS_ACCEPTED
    if estado == "RECHAZADO" or rh_estado == "RECHAZADO":
        return DTEOutbox.STATUS_REJECTED
    if status_code in {401, 403} or error_type == "AUTH":
        return DTEOutbox.STATUS_FAILED
    if status_code in {500, 502, 503, 504} or not status_code:
        return DTEOutbox.STATUS_PENDING
    if 400 <= status_code < 500:
        return DTEOutbox.STATUS_FAILED
    if status_code in {200, 201}:
        return DTEOutbox.STATUS_SENT
    return DTEOutbox.STATUS_PENDING


def is_dte_api_up() -> bool:
    from apps.dte.monitor import DTE_API_STATUS

    if DTE_API_STATUS == "UP":
        return True
    if DTE_API_STATUS == "DOWN":
        return False
    return True


def _sync_order_invoice(order_id: int, outbox_status: str, response_body: dict, error_message: str) -> None:
    invoice = OrderInvoice.objects.filter(order_id=order_id).first()
    if not invoice:
        return

    status_map = {
        DTEOutbox.STATUS_ACCEPTED: ("sent", DTERecord.STATUS_ACCEPTED),
        DTEOutbox.STATUS_REJECTED: ("failed", DTERecord.STATUS_REJECTED),
        DTEOutbox.STATUS_FAILED: ("failed", DTERecord.STATUS_REJECTED),
        DTEOutbox.STATUS_PENDING: ("pending", DTERecord.STATUS_PENDING),
        DTEOutbox.STATUS_SENT: ("pending", DTERecord.STATUS_PENDING),
    }
    invoice_status, dte_status = status_map.get(outbox_status, ("pending", DTERecord.STATUS_PENDING))
    invoice.status = invoice_status
    invoice.dte_status = dte_status
    invoice.hacienda_response = response_body or {}
    invoice.last_error = error_message or ""
    invoice.last_dte_error = error_message or ""
    if outbox_status == DTEOutbox.STATUS_ACCEPTED:
        invoice.sent_at = timezone.now()
    invoice.save(update_fields=["status", "dte_status", "hacienda_response", "last_error", "last_dte_error", "sent_at", "updated_at"])


def enqueue_dte(order_id: int, payload: dict, payment_id: int | None = None) -> DTEOutbox:
    return DTEOutbox.objects.create(order_id=order_id, payment_id=payment_id, payload_json=payload, status=DTEOutbox.STATUS_PENDING)


def send_outbox_entry(outbox: DTEOutbox, path: str) -> DTEOutbox:
    now = timezone.now()
    outbox.attempts += 1
    outbox.last_attempt_at = now

    result = DTEClient().send(
        path=path,
        payload=outbox.payload_json,
        order_id=outbox.order_id,
        payment_id=outbox.payment_id,
        branch_id=outbox.order.branch_id,
        attempt_number=outbox.attempts,
    )
    resolved_status = classify_outbox_status(result.status_code, result.json_body, result.error_type)

    outbox.status = resolved_status
    outbox.response_status_code = result.status_code or None
    outbox.response_body = result.text_body or json.dumps(result.json_body, ensure_ascii=False)
    outbox.error_message = result.error_message or ""
    outbox.save(update_fields=["attempts", "last_attempt_at", "status", "response_status_code", "response_body", "error_message", "updated_at"])

    _sync_order_invoice(outbox.order_id, outbox.status, result.json_body, outbox.error_message)
    return outbox


def process_pending_dtes(limit: int = 50) -> int:
    if not is_dte_api_up():
        return 0

    max_retries = int(getattr(settings, "DTE_MAX_RETRIES", 5) or 5)
    backoff_seconds = int(getattr(settings, "DTE_RETRY_BACKOFF_SECONDS", 30) or 30)
    retry_before = timezone.now() - timedelta(seconds=backoff_seconds)

    pending = (
        DTEOutbox.objects.select_related("order")
        .filter(status=DTEOutbox.STATUS_PENDING, attempts__lt=max_retries)
        .filter(Q(last_attempt_at__isnull=True) | Q(last_attempt_at__lte=retry_before))
        .order_by("created_at")[:limit]
    )

    processed = 0
    for outbox in pending:
        if outbox.attempts >= max_retries:
            outbox.status = DTEOutbox.STATUS_FAILED
            outbox.error_message = f"Max retries reached ({max_retries})"
            outbox.save(update_fields=["status", "error_message", "updated_at"])
            _sync_order_invoice(outbox.order_id, outbox.status, {}, outbox.error_message)
            continue

        try:
            path = "/api/v1/dte/factura"
            dte_type = outbox.payload_json.get("dte", {}).get("identificacion", {}).get("tipoDte")
            if dte_type == "03":
                path = "/api/v1/dte/credito-fiscal"
            send_outbox_entry(outbox, path=path)
            processed += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("[DTE OUTBOX] process_pending_dtes error outbox_id=%s", outbox.id)
            outbox.error_message = str(exc)
            outbox.save(update_fields=["error_message", "updated_at"])

    DTEOutbox.objects.filter(status=DTEOutbox.STATUS_PENDING, attempts__gte=max_retries).update(status=DTEOutbox.STATUS_FAILED, error_message="Max retries reached")
    return processed


def enqueue_or_send_immediately(order_id: int, payment_id: int | None, payload: dict, path: str) -> DTEOutbox:
    with transaction.atomic():
        outbox = enqueue_dte(order_id=order_id, payment_id=payment_id, payload=payload)
        if is_dte_api_up():
            send_outbox_entry(outbox, path=path)
        else:
            logger.warning("[DTE OUTBOX] API DOWN, queued as PENDING order_id=%s outbox_id=%s", order_id, outbox.id)
        return outbox
