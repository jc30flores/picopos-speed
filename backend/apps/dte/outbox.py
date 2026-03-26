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
from apps.dte.monitor import check_health_now, get_monitor
from apps.orders.models import OrderInvoice

DTE_LOGGER = logging.getLogger("apps.dte")


def _preview(text: str, max_len: int = 500) -> str:
    raw = (text or "").replace("\n", " ").strip()
    return raw[:max_len]


def _extract(payload: dict) -> tuple[str, str]:
    ident = (payload or {}).get("dte", {}).get("identificacion", {})
    return str(ident.get("numeroControl") or ""), str(ident.get("codigoGeneracion") or "")


def parse_response_outcome(body: dict) -> str:
    data = body or {}
    candidates = [
        str(data.get("estado") or "").upper(),
        str(data.get("status") or "").upper(),
        str(data.get("result") or "").upper(),
        str((data.get("respuesta_hacienda") or {}).get("estado") or "").upper(),
    ]
    truthy = any(bool(data.get(k)) for k in ["aceptado", "accepted"])
    falsy = any(bool(data.get(k)) for k in ["rechazado", "rejected"])

    if truthy or any(v in {"ACEPTADO", "ACCEPTED", "PROCESADO", "RECIBIDO", "OK"} for v in candidates):
        return DTEOutbox.STATUS_ACCEPTED
    if falsy or any(v in {"RECHAZADO", "REJECTED", "ERROR"} for v in candidates):
        return DTEOutbox.STATUS_REJECTED
    return DTEOutbox.STATUS_SENT


def _sync_invoice(outbox: DTEOutbox, response_body: dict) -> None:
    invoice = OrderInvoice.objects.filter(order_id=outbox.order_id).first()
    if not invoice:
        return

    status_map = {
        DTEOutbox.STATUS_ACCEPTED: ("sent", DTERecord.STATUS_ACCEPTED),
        DTEOutbox.STATUS_REJECTED: ("failed", DTERecord.STATUS_REJECTED),
        DTEOutbox.STATUS_FAILED: ("failed", DTERecord.STATUS_REJECTED),
        DTEOutbox.STATUS_PENDING: ("pending", DTERecord.STATUS_PENDING),
        DTEOutbox.STATUS_SENDING: ("pending", DTERecord.STATUS_PENDING),
        DTEOutbox.STATUS_SENT: ("pending", DTERecord.STATUS_PENDING),
    }
    invoice_status, dte_status = status_map.get(outbox.status, ("pending", DTERecord.STATUS_PENDING))
    invoice.status = invoice_status
    invoice.dte_status = dte_status
    invoice.hacienda_response = response_body or {}
    invoice.last_error = outbox.error_message or ""
    invoice.last_dte_error = outbox.error_message or ""
    if outbox.status == DTEOutbox.STATUS_ACCEPTED:
        invoice.sent_at = timezone.now()
    invoice.save(update_fields=["status", "dte_status", "hacienda_response", "last_error", "last_dte_error", "sent_at", "updated_at"])


def _health_snapshot(stale_seconds: int) -> tuple[bool, int | None, str]:
    snapshot = get_monitor().get_cached_snapshot()
    now_ts = timezone.now().timestamp()
    last_checked = snapshot.last_checked_at or 0
    is_stale = (now_ts - last_checked) > stale_seconds

    if is_stale:
        snapshot = check_health_now(force_log=True)

    return snapshot.is_up, snapshot.status_code, snapshot.body


def _compute_backoff(attempts: int) -> timedelta:
    base = int(getattr(settings, "DTE_RETRY_BACKOFF_SECONDS", 30) or 30)
    return timedelta(seconds=base * max(1, attempts))


def _save_result(outbox: DTEOutbox, *, status: str, response_status_code: int | None, response_body: str, error_message: str = "") -> None:
    outbox.status = status
    outbox.response_status_code = response_status_code
    outbox.response_body = response_body
    outbox.error_message = error_message
    outbox.save(update_fields=["status", "response_status_code", "response_body", "error_message", "updated_at"])


def _endpoint_for_payload(payload: dict) -> str:
    tipo = str((payload or {}).get("dte", {}).get("identificacion", {}).get("tipoDte") or "01")
    return {
        "01": "/api/v1/dte/factura",
        "03": "/api/v1/dte/credito-fiscal",
        "14": "/api/v1/dte/sujeto-excluido",
        "05": "/api/v1/dte/nota-credito",
    }.get(tipo, "/api/v1/dte/factura")


def send_or_queue_dte(order, payment, payload: dict) -> DTEOutbox:
    numero_control, codigo_generacion = _extract(payload)
    with transaction.atomic():
        outbox = DTEOutbox.objects.create(
            order=order,
            payment=payment,
            numero_control=numero_control,
            codigo_generacion=codigo_generacion,
            payload_json=payload,
            payload=payload,
            status=DTEOutbox.STATUS_PENDING,
        )

        stale_seconds = 2 * int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10)
        is_up, health_status, health_body = _health_snapshot(stale_seconds=stale_seconds)
        outbox.last_health_status = health_status
        outbox.last_health_body = health_body or ""

        if not is_up or health_status != 200:
            outbox.status = DTEOutbox.STATUS_PENDING
            outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts + 1)
            outbox.save(update_fields=["status", "next_attempt_at", "last_health_status", "last_health_body", "updated_at"])
            DTE_LOGGER.info(
                "[DTE] QUEUED order=%s payment=%s reason=health_down code=%s body_preview=%s",
                order.id,
                getattr(payment, "id", None),
                health_status,
                _preview(health_body),
            )
            return outbox

        outbox.status = DTEOutbox.STATUS_SENDING
        outbox.attempts += 1
        outbox.last_attempt_at = timezone.now()
        outbox.save(update_fields=["status", "attempts", "last_attempt_at", "last_health_status", "last_health_body", "updated_at"])

        endpoint = _endpoint_for_payload(payload)
        try:
            result = DTEClient().send(
                path=endpoint,
                payload=payload,
                order_id=order.id,
                payment_id=getattr(payment, "id", None),
                branch_id=order.branch_id,
                attempt_number=outbox.attempts,
            )

            parsed = result.json_body if isinstance(result.json_body, dict) else {}
            inferred = parse_response_outcome(parsed)

            if result.status_code in {401, 403}:
                final_status = DTEOutbox.STATUS_FAILED
            elif 500 <= (result.status_code or 0) <= 599:
                final_status = DTEOutbox.STATUS_PENDING
            elif 400 <= (result.status_code or 0) <= 499:
                final_status = DTEOutbox.STATUS_FAILED
            else:
                final_status = inferred

            outbox.status = final_status
            outbox.response_status_code = result.status_code or None
            outbox.response_body = result.text_body or json.dumps(parsed, ensure_ascii=False)
            outbox.error_message = result.error_message or ""
            if final_status == DTEOutbox.STATUS_PENDING:
                outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts)
            else:
                outbox.next_attempt_at = None
            outbox.save(update_fields=["status", "response_status_code", "response_body", "error_message", "next_attempt_at", "updated_at"])

            DTE_LOGGER.info(
                "[DTE] RESULT order=%s payment=%s status=%s http=%s",
                order.id,
                getattr(payment, "id", None),
                final_status,
                result.status_code,
            )
            _sync_invoice(outbox, parsed)
            return outbox
        except Exception as exc:  # noqa: BLE001
            outbox.status = DTEOutbox.STATUS_PENDING
            outbox.error_message = str(exc)
            outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts)
            outbox.save(update_fields=["status", "error_message", "next_attempt_at", "updated_at"])
            DTE_LOGGER.exception("[DTE] send_or_queue_dte exception order=%s payment=%s", order.id, getattr(payment, "id", None))
            _sync_invoice(outbox, {})
            return outbox


def _resend_existing_outbox(outbox: DTEOutbox) -> DTEOutbox:
    payload = outbox.payload or outbox.payload_json or {}
    outbox.status = DTEOutbox.STATUS_SENDING
    outbox.attempts += 1
    outbox.last_attempt_at = timezone.now()
    outbox.save(update_fields=["status", "attempts", "last_attempt_at", "updated_at"])

    endpoint = _endpoint_for_payload(payload)
    result = DTEClient().send(
        path=endpoint,
        payload=payload,
        order_id=outbox.order_id,
        payment_id=outbox.payment_id,
        branch_id=outbox.order.branch_id,
        attempt_number=outbox.attempts,
    )
    parsed = result.json_body if isinstance(result.json_body, dict) else {}
    inferred = parse_response_outcome(parsed)

    if result.status_code in {401, 403}:
        final_status = DTEOutbox.STATUS_FAILED
    elif 500 <= (result.status_code or 0) <= 599:
        final_status = DTEOutbox.STATUS_PENDING
    elif 400 <= (result.status_code or 0) <= 499:
        final_status = DTEOutbox.STATUS_FAILED
    else:
        final_status = inferred

    outbox.status = final_status
    outbox.response_status_code = result.status_code or None
    outbox.response_body = result.text_body or json.dumps(parsed, ensure_ascii=False)
    outbox.error_message = result.error_message or ""
    outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts) if final_status == DTEOutbox.STATUS_PENDING else None
    outbox.save(update_fields=["status", "response_status_code", "response_body", "error_message", "next_attempt_at", "updated_at"])
    _sync_invoice(outbox, parsed)
    DTE_LOGGER.info(
        "[DTE] RESULT order=%s payment=%s status=%s http=%s",
        outbox.order_id,
        outbox.payment_id,
        final_status,
        result.status_code,
    )
    return outbox


def process_pending_outbox(limit: int = 50) -> int:
    is_up, health_status, health_body = _health_snapshot(
        stale_seconds=2 * int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10)
    )
    if not is_up or health_status != 200:
        DTE_LOGGER.info("[DTE] process_pending_outbox skipped health code=%s body_preview=%s", health_status, _preview(health_body))
        return 0

    max_retries = int(getattr(settings, "DTE_MAX_RETRIES", 5) or 5)
    now = timezone.now()
    pending = (
        DTEOutbox.objects.select_related("order", "payment")
        .filter(status=DTEOutbox.STATUS_PENDING, attempts__lt=max_retries)
        .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
        .order_by("created_at")[:limit]
    )

    processed = 0
    for outbox in pending:
        try:
            processed_outbox = _resend_existing_outbox(outbox)
            if processed_outbox.status in {DTEOutbox.STATUS_ACCEPTED, DTEOutbox.STATUS_REJECTED, DTEOutbox.STATUS_SENT, DTEOutbox.STATUS_FAILED, DTEOutbox.STATUS_PENDING}:
                processed += 1
        except Exception:  # noqa: BLE001
            DTE_LOGGER.exception("[DTE] process_pending_outbox exception outbox_id=%s", outbox.id)

    DTEOutbox.objects.filter(status=DTEOutbox.STATUS_PENDING, attempts__gte=max_retries).update(
        status=DTEOutbox.STATUS_FAILED,
        error_message="Max retries reached",
        next_attempt_at=None,
    )
    return processed
