from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError as DjangoOperationalError, connection, close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.dte.client import DTEClient
from apps.dte.models import DTEOutbox, DTERecord
from apps.dte.monitor import STATE_UP, check_health_now, get_monitor
from apps.dte.services.dte_service import build_payload_cf
from apps.dte.services.emisor import get_emisor_nit, payload_emisor_nit
from apps.orders.models import OrderInvoice

DTE_LOGGER = logging.getLogger("apps.dte")
_OUTBOX_WORKER_STARTED = False
_OUTBOX_WORKER_LOCK = threading.Lock()
_LAST_DB_DOWN_LOG_TS = 0.0
_LAST_HTTP_DOWN_LOG_TS = 0.0
_LAST_IDLE_LOG_TS = 0.0

CIRCUIT_FAIL_COUNT = "dte:circuit:fail_count"
CIRCUIT_OPEN_UNTIL = "dte:circuit:open_until"


def _preview(text: str, max_len: int = 500) -> str:
    return (text or "").replace("\n", " ").strip()[:max_len]


def _log_throttled(level: str, key: str, message: str, *args) -> None:
    global _LAST_DB_DOWN_LOG_TS, _LAST_HTTP_DOWN_LOG_TS
    now = time.time()
    cooldown = float(getattr(settings, "DTE_ERROR_LOG_COOLDOWN_SECONDS", 30) or 30)
    if key == "db":
        if now - _LAST_DB_DOWN_LOG_TS < cooldown:
            return
        _LAST_DB_DOWN_LOG_TS = now
    elif key == "http":
        if now - _LAST_HTTP_DOWN_LOG_TS < cooldown:
            return
        _LAST_HTTP_DOWN_LOG_TS = now
    getattr(DTE_LOGGER, level, DTE_LOGGER.warning)(message, *args)


def _looks_like_network_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("timed out", "name resolution", "connection aborted", "connection refused", "failed to establish a new connection"))


def _extract(payload: dict) -> tuple[str, str]:
    ident = (payload or {}).get("dte", {}).get("identificacion", {})
    return str(ident.get("numeroControl") or ""), str(ident.get("codigoGeneracion") or "")


def _payload_dir() -> str:
    return str(getattr(settings, "DTE_LOG_DIR", "tmp/dte_payloads") or "tmp/dte_payloads")


def _save_payload_file(*, outbox_id: int | None, payload_text: str, numero_control: str, codigo_generacion: str) -> None:
    if not bool(getattr(settings, "DTE_LOG_TO_FILE", False)):
        return
    os.makedirs(_payload_dir(), exist_ok=True)
    safe_control = (numero_control or "").replace("/", "_").replace(":", "_").replace(" ", "_")
    safe_codigo = (codigo_generacion or "").replace("/", "_").replace(":", "_").replace(" ", "_")
    if safe_control or safe_codigo:
        filename = f"{safe_control or 'nocontrol'}_{safe_codigo or 'nocodigo'}_request.json"
    else:
        ts = timezone.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{ts}_outbox_{outbox_id or 'na'}_request.json"
    file_path = os.path.join(_payload_dir(), filename)
    with open(file_path, "w", encoding="utf-8") as fh:
        fh.write(payload_text)
    DTE_LOGGER.info("[CF01] REQUEST saved_to=%s bytes=%s", file_path, len(payload_text.encode("utf-8")))


def _log_full_payload(*, payload: dict, order_id: int | None, payment_id: int | None, numero_control: str, codigo_generacion: str, outbox_id: int | None = None, endpoint_url: str = "") -> None:
    payload_text = json.dumps(payload or {}, ensure_ascii=False, indent=2, default=str)
    if not bool(getattr(settings, "DTE_DEBUG_LOG_PAYLOAD", getattr(settings, "DTE_LOG_PAYLOAD_FULL", False))):
        DTE_LOGGER.info("[CF01] REQUEST BEGIN invoice=%s order=%s payment=%s numeroControl=%s codigoGeneracion=%s", order_id, order_id, payment_id, numero_control, codigo_generacion)
        return
    if endpoint_url:
        DTE_LOGGER.info("ENDPOINT DTE: %s", endpoint_url)
    DTE_LOGGER.info("JSON DTE ENVIO:\n%s", payload_text)
    DTE_LOGGER.info(
        "[CF01] REQUEST BEGIN invoice=%s order=%s payment=%s numeroControl=%s codigoGeneracion=%s",
        order_id,
        order_id,
        payment_id,
        numero_control,
        codigo_generacion,
    )
    DTE_LOGGER.info("[CF01] REQUEST:\n%s", payload_text)
    DTE_LOGGER.info("[CF01] REQUEST END invoice=%s order=%s payment=%s", order_id, order_id, payment_id)
    _save_payload_file(
        outbox_id=outbox_id,
        payload_text=payload_text,
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
    )


def parse_response_outcome(body: dict) -> str:
    data = body or {}
    if data.get("success") is True:
        return DTEOutbox.STATUS_ACCEPTED
    if data.get("offline") is True:
        return DTEOutbox.STATUS_PENDING
    error = data.get("error") if isinstance(data.get("error"), dict) else {}
    if str(error.get("type") or "").upper() == "TIMEOUT":
        return DTEOutbox.STATUS_PENDING
    values = {
        str(data.get("estado") or "").upper(),
        str(data.get("status") or "").upper(),
        str(data.get("result") or "").upper(),
        str((data.get("respuesta_hacienda") or {}).get("estado") or "").upper(),
    }
    if data.get("aceptado") is True or data.get("accepted") is True or values & {"ACEPTADO", "ACCEPTED", "PROCESADO", "RECIBIDO", "OK"}:
        return DTEOutbox.STATUS_ACCEPTED
    if data.get("rechazado") is True or data.get("rejected") is True or values & {"RECHAZADO", "REJECTED", "ERROR"}:
        return DTEOutbox.STATUS_REJECTED
    return DTEOutbox.STATUS_PENDING


def _classify_final_status(*, result, parsed: dict, inferred: str) -> str:
    status_code = int(result.status_code or 0)
    error_type = str(getattr(result, "error_type", "") or "").upper()

    if parsed.get("success") is True:
        return DTEOutbox.STATUS_ACCEPTED
    if parsed.get("offline") is True or error_type == "TIMEOUT":
        return DTEOutbox.STATUS_PENDING
    if status_code == 0:
        return DTEOutbox.STATUS_PENDING
    if status_code in {429, 502, 503, 504}:
        return DTEOutbox.STATUS_PENDING
    if status_code >= 500:
        return DTEOutbox.STATUS_PENDING
    if status_code in {400, 401, 403, 422}:
        return DTEOutbox.STATUS_FAILED
    if 400 <= status_code < 500:
        return DTEOutbox.STATUS_FAILED
    if inferred == DTEOutbox.STATUS_ACCEPTED:
        return DTEOutbox.STATUS_ACCEPTED
    if inferred == DTEOutbox.STATUS_REJECTED:
        return DTEOutbox.STATUS_FAILED
    return DTEOutbox.STATUS_PENDING


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


def _health_snapshot(stale_seconds: int):
    snapshot = get_monitor().get_cached_snapshot()
    now_ts = timezone.now().timestamp()
    is_stale = (now_ts - (snapshot.last_checked_at or 0)) > stale_seconds
    if is_stale:
        snapshot = check_health_now(force_log=True)
    return snapshot


def _compute_backoff(attempts: int) -> timedelta:
    base = int(getattr(settings, "DTE_BACKOFF_BASE_SECONDS", 10) or 10)
    max_seconds = int(getattr(settings, "DTE_BACKOFF_MAX_SECONDS", 600) or 600)
    exp_seconds = min(max_seconds, base * (2 ** max(0, attempts - 1)))
    jitter = random.randint(0, 3)
    return timedelta(seconds=exp_seconds + jitter)


def _is_circuit_open() -> tuple[bool, float | None]:
    open_until = cache.get(CIRCUIT_OPEN_UNTIL)
    if not open_until:
        return False, None
    if timezone.now().timestamp() < float(open_until):
        return True, float(open_until)
    cache.delete(CIRCUIT_OPEN_UNTIL)
    cache.set(CIRCUIT_FAIL_COUNT, 0, timeout=None)
    return False, None


def _register_send_failure() -> None:
    threshold = int(getattr(settings, "DTE_CIRCUIT_FAIL_THRESHOLD", 3) or 3)
    open_seconds = int(getattr(settings, "DTE_CIRCUIT_OPEN_SECONDS", 60) or 60)
    count = int(cache.get(CIRCUIT_FAIL_COUNT, 0) or 0) + 1
    cache.set(CIRCUIT_FAIL_COUNT, count, timeout=None)
    if count >= threshold:
        open_until = timezone.now().timestamp() + open_seconds
        cache.set(CIRCUIT_OPEN_UNTIL, open_until, timeout=None)


def _reset_circuit() -> None:
    cache.set(CIRCUIT_FAIL_COUNT, 0, timeout=None)
    cache.delete(CIRCUIT_OPEN_UNTIL)


def _endpoint_for_payload(payload: dict) -> str:
    tipo = str((payload or {}).get("dte", {}).get("identificacion", {}).get("tipoDte") or "01")
    return {
        "01": "/api/v1/dte/factura",
        "03": "/api/v1/dte/credito-fiscal",
        "14": "/api/v1/dte/sujeto-excluido",
        "05": "/api/v1/dte/nota-credito",
    }.get(tipo, "/api/v1/dte/factura")


def _repair_payload_nit_if_needed(outbox: DTEOutbox, payload: dict) -> tuple[dict, bool]:
    expected_nit = get_emisor_nit(outbox.order.branch if outbox.order_id else None)
    payload_nit = payload_emisor_nit(payload)
    if payload_nit == expected_nit:
        return payload, False

    ident = (payload or {}).get("dte", {}).get("identificacion", {})
    control_number = str(ident.get("numeroControl") or outbox.numero_control or getattr(outbox.dte_record, "control_number", "") or "")
    generation_code = str(ident.get("codigoGeneracion") or outbox.codigo_generacion or getattr(outbox.dte_record, "generation_code", "") or "")
    ambiente = str(ident.get("ambiente") or getattr(outbox.dte_record, "ambiente", "00") or "00")
    if not control_number or not generation_code:
        outbox.status = DTEOutbox.STATUS_FAILED
        outbox.error_message = "INVALID_EMISOR_NIT_PAYLOAD:missing_identificacion"
        outbox.next_attempt_at = None
        outbox.save(update_fields=["status", "error_message", "next_attempt_at", "updated_at"])
        return payload, False
    try:
        rebuilt = build_payload_cf(outbox.order, control_number=control_number, generation_code=generation_code, ambiente=ambiente)
        rebuilt_nit = payload_emisor_nit(rebuilt)
        if rebuilt_nit != expected_nit:
            raise ValidationError("Rebuilt payload NIT does not match expected NIT.")
        outbox.payload = rebuilt
        outbox.payload_json = rebuilt
        outbox.next_attempt_at = timezone.now()
        outbox.error_message = f"Repaired outbox payload emisor.nit mismatch old={payload_nit or '-'} new={rebuilt_nit}"
        outbox.save(update_fields=["payload", "payload_json", "next_attempt_at", "error_message", "updated_at"])
        DTE_LOGGER.warning(
            "[DTE OUTBOX] Repaired outbox payload emisor.nit mismatch outbox_id=%s order_id=%s old_nit=%s new_nit=%s",
            outbox.id,
            outbox.order_id,
            payload_nit or "-",
            rebuilt_nit,
        )
        return rebuilt, True
    except Exception as exc:  # noqa: BLE001
        outbox.status = DTEOutbox.STATUS_FAILED
        outbox.error_message = f"INVALID_EMISOR_NIT_PAYLOAD:{_preview(str(exc), 180)}"
        outbox.next_attempt_at = None
        outbox.save(update_fields=["status", "error_message", "next_attempt_at", "updated_at"])
        DTE_LOGGER.error(
            "[DTE OUTBOX] Could not repair payload NIT outbox_id=%s order_id=%s err=%s",
            outbox.id,
            outbox.order_id,
            _preview(str(exc), 180),
        )
        return payload, False


def _apply_result(outbox: DTEOutbox, result) -> DTEOutbox:
    parsed = result.json_body if isinstance(result.json_body, dict) else {}
    inferred = parse_response_outcome(parsed)
    final_status = _classify_final_status(result=result, parsed=parsed, inferred=inferred)

    outbox.status = final_status
    outbox.response_status_code = result.status_code or None
    outbox.response_body = result.text_body or json.dumps(parsed, ensure_ascii=False)
    outbox.error_message = result.error_message or ""
    outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts) if final_status == DTEOutbox.STATUS_PENDING else None
    outbox.save(update_fields=["status", "response_status_code", "response_body", "error_message", "next_attempt_at", "updated_at"])

    if final_status == DTEOutbox.STATUS_PENDING:
        _register_send_failure()
        DTE_LOGGER.info("[DTE] QUEUED order=%s payment=%s reason=retryable http=%s", outbox.order_id, outbox.payment_id, result.status_code)
    elif final_status in {DTEOutbox.STATUS_ACCEPTED, DTEOutbox.STATUS_FAILED}:
        _reset_circuit()

    DTE_LOGGER.info(
        "[DTE] RESULT order=%s payment=%s attempt=%s status=%s http=%s elapsed_ms=%s body_preview=%s",
        outbox.order_id,
        outbox.payment_id,
        outbox.attempts,
        final_status,
        result.status_code,
        result.elapsed_ms,
        _preview(outbox.response_body),
    )
    if outbox.dte_record_id:
        record_status = {
            DTEOutbox.STATUS_ACCEPTED: DTERecord.STATUS_ACCEPTED,
            DTEOutbox.STATUS_FAILED: DTERecord.STATUS_REJECTED,
            DTEOutbox.STATUS_PENDING: DTERecord.STATUS_PENDING,
            DTEOutbox.STATUS_SENDING: DTERecord.STATUS_PENDING,
            DTEOutbox.STATUS_SENT: DTERecord.STATUS_PENDING,
        }.get(final_status, DTERecord.STATUS_PENDING)
        DTERecord.objects.filter(pk=outbox.dte_record_id).update(
            status=record_status,
            response_payload=parsed,
            response_text=outbox.response_body or "",
            error_message=outbox.error_message or "",
            last_error_message=outbox.error_message or "",
            last_error_code="HTTP_ERROR" if (result.status_code and result.status_code >= 400) else "",
            last_sent_at=timezone.now(),
            attempts=outbox.attempts,
            send_attempts=outbox.attempts,
            updated_at=timezone.now(),
        )
    DTE_LOGGER.info("PERSIST order_id=%s dte_record_id=%s status=%s", outbox.order_id, outbox.dte_record_id, final_status)
    _sync_invoice(outbox, parsed)
    return outbox


def process_pending_dtes(limit: int = 25, batch_size: int = 25, backoff_seconds: int | None = None) -> int:
    _ = batch_size
    if backoff_seconds:
        setattr(settings, "DTE_RETRY_BACKOFF_SECONDS", int(backoff_seconds))
    return process_pending_outbox(limit=limit)


def _get_or_create_pending_outbox(order, payment, payload: dict, dte_record: DTERecord | None = None) -> DTEOutbox:
    numero_control, codigo_generacion = _extract(payload)
    existing = (
        DTEOutbox.objects.filter(
            order=order,
            payment=payment,
            dte_record=dte_record,
            status__in=[DTEOutbox.STATUS_PENDING, DTEOutbox.STATUS_SENDING],
        )
        .order_by("-created_at")
        .first()
    )
    if existing:
        return existing
    endpoint_url = f"{(getattr(settings, 'DTE_BASE_URL', '') or '').rstrip('/')}{_endpoint_for_payload(payload)}"
    outbox = DTEOutbox.objects.create(
        order=order,
        payment=payment,
        dte_record=dte_record,
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        payload_json=payload,
        payload=payload,
        status=DTEOutbox.STATUS_PENDING,
    )
    _log_full_payload(
        payload=payload,
        order_id=order.id,
        payment_id=getattr(payment, "id", None),
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        outbox_id=outbox.id,
        endpoint_url=endpoint_url,
    )
    return outbox


def send_or_queue_dte(order, payment, payload: dict, dte_record: DTERecord | None = None, *, attempt_immediate: bool = True) -> DTEOutbox:
    with transaction.atomic():
        outbox = _get_or_create_pending_outbox(order, payment, payload, dte_record=dte_record)
        if not attempt_immediate:
            outbox.status = DTEOutbox.STATUS_PENDING
            outbox.next_attempt_at = outbox.next_attempt_at or timezone.now()
            outbox.save(update_fields=["status", "next_attempt_at", "updated_at"])
            DTE_LOGGER.info("[DTE OUTBOX] queued id=%s order=%s payment=%s mode=async_only", outbox.id, order.id, getattr(payment, "id", None))
            _sync_invoice(outbox, {})
            return outbox

        stale_seconds = 2 * int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10)
        health = _health_snapshot(stale_seconds=stale_seconds)
        outbox.last_health_status = health.health_status_code
        outbox.last_health_body = health.health_body

        circuit_open, open_until = _is_circuit_open()
        if circuit_open:
            outbox.status = DTEOutbox.STATUS_PENDING
            outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts + 1)
            outbox.save(update_fields=["status", "next_attempt_at", "last_health_status", "last_health_body", "updated_at"])
            DTE_LOGGER.info("[DTE OUTBOX] queued id=%s order=%s payment=%s reason=circuit_open open_until=%s", outbox.id, order.id, getattr(payment, "id", None), open_until)
            return outbox

        if health.state != STATE_UP:
            outbox.status = DTEOutbox.STATUS_PENDING
            outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts + 1)
            outbox.save(update_fields=["status", "next_attempt_at", "last_health_status", "last_health_body", "updated_at"])
            DTE_LOGGER.info(
                "[DTE OUTBOX] queued id=%s order=%s payment=%s reason=health_%s health_code=%s factura_code=%s health_body_preview=%s factura_body_preview=%s",
                outbox.id,
                order.id,
                getattr(payment, "id", None),
                health.state.lower(),
                health.health_status_code,
                health.factura_code,
                _preview(health.health_body),
                _preview(health.factura_body),
            )
            return outbox

        outbox.status = DTEOutbox.STATUS_SENDING
        outbox.attempts += 1
        outbox.last_attempt_at = timezone.now()
        outbox.save(update_fields=["status", "attempts", "last_attempt_at", "last_health_status", "last_health_body", "updated_at"])

        try:
            result = DTEClient().send(
                path=_endpoint_for_payload(payload),
                payload=payload,
                order_id=order.id,
                payment_id=getattr(payment, "id", None),
                branch_id=order.branch_id,
                attempt_number=outbox.attempts,
            )
            return _apply_result(outbox, result)
        except Exception:  # noqa: BLE001
            outbox.status = DTEOutbox.STATUS_PENDING
            outbox.error_message = "network_exception"
            outbox.next_attempt_at = timezone.now() + _compute_backoff(outbox.attempts)
            outbox.save(update_fields=["status", "error_message", "next_attempt_at", "updated_at"])
            _register_send_failure()
            DTE_LOGGER.exception("[DTE] send_or_queue_dte exception order=%s payment=%s", order.id, getattr(payment, "id", None))
            _sync_invoice(outbox, {})
            return outbox


def _resend_existing_outbox(outbox: DTEOutbox) -> DTEOutbox:
    payload = outbox.payload or outbox.payload_json or {}
    payload, _ = _repair_payload_nit_if_needed(outbox, payload)
    outbox.refresh_from_db(fields=["status"])
    if outbox.status == DTEOutbox.STATUS_FAILED:
        _sync_invoice(outbox, {})
        return outbox
    numero_control, codigo_generacion = _extract(payload)
    endpoint_url = f"{(getattr(settings, 'DTE_BASE_URL', '') or '').rstrip('/')}{_endpoint_for_payload(payload)}"
    _log_full_payload(
        payload=payload,
        order_id=outbox.order_id,
        payment_id=outbox.payment_id,
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        outbox_id=outbox.id,
        endpoint_url=endpoint_url,
    )
    if outbox.status != DTEOutbox.STATUS_PENDING:
        return outbox
    outbox.status = DTEOutbox.STATUS_SENDING
    outbox.attempts += 1
    outbox.last_attempt_at = timezone.now()
    outbox.save(update_fields=["status", "attempts", "last_attempt_at", "updated_at"])
    DTE_LOGGER.info(
        "[DTE OUTBOX] processing id=%s order=%s attempt=%s next_attempt_at=%s",
        outbox.id,
        outbox.order_id,
        outbox.attempts,
        outbox.next_attempt_at,
    )

    try:
        result = DTEClient().send(
            path=_endpoint_for_payload(payload),
            payload=payload,
            order_id=outbox.order_id,
            payment_id=outbox.payment_id,
            branch_id=outbox.order.branch_id,
            attempt_number=outbox.attempts,
        )
        updated = _apply_result(outbox, result)
    except Exception as exc:  # noqa: BLE001
        if not _looks_like_network_error(exc):
            raise
        backoff = _compute_backoff(outbox.attempts)
        outbox.status = DTEOutbox.STATUS_PENDING
        outbox.error_message = f"HTTP_ERROR:{exc.__class__.__name__}"
        outbox.next_attempt_at = timezone.now() + backoff
        outbox.save(update_fields=["status", "error_message", "next_attempt_at", "updated_at"])
        _register_send_failure()
        _sync_invoice(outbox, {})
        _log_throttled(
            "warning",
            "http",
            "[DTE OUTBOX] HTTP_TIMEOUT retry_in=%ss outbox_id=%s err=%s",
            int(backoff.total_seconds()),
            outbox.id,
            _preview(str(exc), 180),
        )
        return outbox
    DTE_LOGGER.info(
        "[DTE OUTBOX] result id=%s status=%s http=%s reason=%s",
        updated.id,
        updated.status,
        updated.response_status_code,
        updated.error_message or "-",
    )
    return updated


def process_pending_outbox(limit: int = 50) -> int:
    global _LAST_IDLE_LOG_TS
    health = _health_snapshot(stale_seconds=2 * int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10))
    circuit_open, open_until = _is_circuit_open()

    if health.state != STATE_UP:
        DTE_LOGGER.info(
            "[DTE] process_pending_outbox skipped reason=health_%s health_code=%s factura_code=%s health_body_preview=%s",
            health.state.lower(),
            health.health_status_code,
            health.factura_code,
            _preview(health.health_body),
        )
        return 0
    if circuit_open:
        DTE_LOGGER.info("[DTE] process_pending_outbox skipped reason=circuit_open open_until=%s", open_until)
        return 0

    max_retries = int(getattr(settings, "DTE_MAX_RETRIES", 5) or 5)
    stuck_timeout_seconds = int(getattr(settings, "DTE_PROCESSING_TIMEOUT_SECONDS", 120) or 120)
    now = timezone.now()
    DTEOutbox.objects.filter(
        status=DTEOutbox.STATUS_SENDING,
        last_attempt_at__lt=now - timedelta(seconds=stuck_timeout_seconds),
    ).update(
        status=DTEOutbox.STATUS_PENDING,
        next_attempt_at=now,
        error_message="Recovered from stuck PROCESSING state",
    )
    with transaction.atomic():
        pending_ids = list(
            DTEOutbox.objects.select_for_update(skip_locked=True)
            .filter(status=DTEOutbox.STATUS_PENDING, attempts__lt=max_retries)
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now))
            .order_by("created_at")
            .values_list("id", flat=True)[:limit]
        )
    pending = DTEOutbox.objects.select_related("order", "payment").filter(id__in=pending_ids).order_by("created_at")

    if pending_ids:
        DTE_LOGGER.info("[DTE OUTBOX] picked=%s", len(pending_ids))
    else:
        idle_every = int(getattr(settings, "DTE_LOG_IDLE_EVERY_SECONDS", 300) or 300)
        now_ts = time.time()
        if now_ts - _LAST_IDLE_LOG_TS >= idle_every:
            DTE_LOGGER.debug("[DTE OUTBOX] idle queue_size=0")
            _LAST_IDLE_LOG_TS = now_ts
    processed = 0
    for outbox in pending:
        try:
            _resend_existing_outbox(outbox)
            processed += 1
        except DjangoOperationalError as exc:
            try:
                close_old_connections()
                connection.close()
            except Exception:  # noqa: BLE001
                pass
            _log_throttled("error", "db", "[DTE OUTBOX] DB_DOWN retry_in=%ss err=%s", 1, _preview(str(exc), 180))
        except Exception:  # noqa: BLE001
            _log_throttled("warning", "db", "[DTE OUTBOX] process exception outbox_id=%s", outbox.id)

    DTEOutbox.objects.filter(status=DTEOutbox.STATUS_PENDING, attempts__gte=max_retries).update(
        status=DTEOutbox.STATUS_FAILED,
        error_message="Max retries reached",
        next_attempt_at=None,
    )
    return processed


def _outbox_worker_loop() -> None:
    interval = float(getattr(settings, "DTE_OUTBOX_INTERVAL", 2) or 2)
    batch_size = int(getattr(settings, "DTE_OUTBOX_CONCURRENCY", 1) or 1)
    db_backoff_seconds = 1.0
    while True:
        close_old_connections()
        try:
            process_pending_outbox(limit=batch_size)
            db_backoff_seconds = 1.0
        except DjangoOperationalError as exc:
            try:
                close_old_connections()
                connection.close()
            except Exception:  # noqa: BLE001
                pass
            _log_throttled(
                "error",
                "db",
                "[DTE OUTBOX] DB_DOWN retry_in=%ss err=%s",
                int(db_backoff_seconds),
                _preview(str(exc), 180),
            )
            time.sleep(db_backoff_seconds)
            db_backoff_seconds = min(db_backoff_seconds * 2, 30.0)
            continue
        except Exception:  # noqa: BLE001
            _log_throttled("warning", "db", "[DTE OUTBOX] worker loop error (summarized)")
        time.sleep(interval)


def start_outbox_worker() -> bool:
    global _OUTBOX_WORKER_STARTED
    with _OUTBOX_WORKER_LOCK:
        if _OUTBOX_WORKER_STARTED:
            return False
        if not bool(getattr(settings, "DTE_OUTBOX_WORKER_ENABLED", True)):
            return False
        interval = float(getattr(settings, "DTE_OUTBOX_INTERVAL", 2) or 2)
        concurrency = int(getattr(settings, "DTE_OUTBOX_CONCURRENCY", 1) or 1)
        DTE_LOGGER.info("[DTE OUTBOX] starting worker interval=%ss concurrency=%s", interval, concurrency)
        thread = threading.Thread(target=_outbox_worker_loop, daemon=True, name="dte-outbox-worker")
        thread.start()
        _OUTBOX_WORKER_STARTED = True
        return True
