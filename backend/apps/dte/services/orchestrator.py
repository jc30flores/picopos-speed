from __future__ import annotations

import json
import logging
from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.outbox import send_or_queue_dte
from apps.dte.services.active_branch import get_active_branch
from apps.dte.services.control import build_generation_code, next_control_number
from apps.dte.services.dte_service import (
    DTEPreflightError,
    build_payload_cf,
    interpret_dte_response,
)
from apps.dte.services.ambiente import normalize_ambiente, resolve_ambiente_from_env, resolve_ambiente_with_source
from apps.dte.services.delivery import deliver_dte_to_client
from apps.dte.services.delivery_config import INTERNAL_BILLING_EMAIL
from apps.dte.services.availability import evaluate_record_actions
from apps.dte.services.customer_rules import is_consumer_final_order
from apps.orders.models import Order, OrderInvoice
from apps.orders.services.snapshots import persist_sale_snapshot

DTE_LOGGER = logging.getLogger("apps.dte")


def _normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _is_valid_email(value: str | None) -> bool:
    email = str(value or "").strip()
    return bool(email and "@" in email and "." in email.split("@")[-1] and " " not in email)


def _normalize_phone(value: str | None) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) == 8:
        return f"503{digits}"
    return digits


def _is_placeholder_phone(value: str | None) -> bool:
    digits = _normalize_phone(value)
    return not digits or digits in {"00000000", "000000000", "0000000000", "50300000000"} or set(digits) == {"0"}


def _safe_name(value: str | None) -> str:
    return str(value or "").strip().upper()


def _maybe_auto_send_delivery(record: DTERecord) -> None:
    if record.status != DTERecord.STATUS_ACCEPTED:
        return
    rh = (record.response_payload or {}).get("respuesta_hacienda") if isinstance(record.response_payload, dict) else {}
    if not isinstance(rh, dict):
        rh = {}
    estado = str(rh.get("estado") or record.estado_mh or "").strip().upper()
    sello = str(record.sello_recibido or record.sello_recepcion or rh.get("selloRecibido") or "").strip()
    if estado not in {"ACEPTADO", "PROCESADO", "RECIBIDO"} and not sello:
        return

    customer = getattr(record.order, "customer", None)
    receptor_name = _safe_name((record.request_payload or {}).get("dte", {}).get("receptor", {}).get("nombre")) or _safe_name(getattr(customer, "name", ""))
    receptor_email = _normalize_email((record.request_payload or {}).get("dte", {}).get("receptor", {}).get("correo") or getattr(customer, "correo", ""))
    emisor_email = _normalize_email((record.request_payload or {}).get("dte", {}).get("emisor", {}).get("correo"))
    receptor_phone = str((record.request_payload or {}).get("dte", {}).get("receptor", {}).get("telefono") or getattr(customer, "telefono", "") or "").strip()
    manual_extra = str(getattr(record.order, "whatsapp_num_cliente", "") or "").strip()

    receptor_email_valid = _is_valid_email(receptor_email)
    receptor_email_same_as_emisor = bool(receptor_email and emisor_email and receptor_email == emisor_email)

    email_should_send = False
    email_reason = ""
    if not receptor_email_valid:
        email_reason = "email_invalid"
    elif receptor_name != "CONSUMIDOR FINAL":
        email_should_send = True
        email_reason = "non_consumer_final"
    elif not receptor_email_same_as_emisor:
        email_should_send = True
        email_reason = "consumer_final_different_email"
    else:
        email_reason = "consumer_final_same_email"

    manual_extra_present = bool(_normalize_phone(manual_extra))
    receptor_phone_placeholder = _is_placeholder_phone(receptor_phone)
    whatsapp_should_send = manual_extra_present or not receptor_phone_placeholder
    whatsapp_reason = "manual_extra" if manual_extra_present else ("dte_receptor_phone" if not receptor_phone_placeholder else "no_valid_phone")

    DTE_LOGGER.info(
        "DTE_AUTO_DELIVERY_EVALUATED dte_record_id=%s order_id=%s codigoGeneracion=%s status=%s email_should_send=%s email_reason=%s whatsapp_should_send=%s whatsapp_reason=%s receptor_name=%s receptor_email_present=%s receptor_email_same_as_emisor=%s receptor_phone_placeholder=%s manual_extra_present=%s",
        record.id, record.order_id, record.codigo_generacion, record.status, email_should_send, email_reason,
        whatsapp_should_send, whatsapp_reason, receptor_name or "UNKNOWN", bool(receptor_email), receptor_email_same_as_emisor,
        receptor_phone_placeholder, manual_extra_present,
    )

    channels: list[str] = []
    if email_should_send:
        channels.append("email")
    else:
        DTE_LOGGER.info("DTE_AUTO_DELIVERY_SKIPPED dte_record_id=%s channel=email reason=%s", record.id, email_reason)
    if whatsapp_should_send:
        channels.append("whatsapp")
    else:
        DTE_LOGGER.info("DTE_AUTO_DELIVERY_SKIPPED dte_record_id=%s channel=whatsapp reason=%s", record.id, whatsapp_reason)
    if not channels:
        return

    for ch, dtype, ok_statuses in (("email", DteDeliveryAttempt.TYPE_EMAIL, {"SENT"}), ("whatsapp", DteDeliveryAttempt.TYPE_WA, {"SENT", "QUEUED"})):
        if ch in channels and DteDeliveryAttempt.objects.filter(dte_record=record, delivery_type=dtype, status__in=ok_statuses).exists():
            DTE_LOGGER.info("DTE_AUTO_DELIVERY_DUPLICATE_SKIP dte_record_id=%s channel=%s reason=already_auto_sent", record.id, ch)
            channels.remove(ch)
    if not channels:
        return

    try:
        if "email" in channels:
            DTE_LOGGER.info("DTE_AUTO_EMAIL_START dte_record_id=%s", record.id)
        if "whatsapp" in channels:
            DTE_LOGGER.info("DTE_AUTO_WHATSAPP_START dte_record_id=%s", record.id)
        result = deliver_dte_to_client(record, channels=tuple(channels), mode="automatic", to_phone=manual_extra or None)
        if "email" in channels:
            DTE_LOGGER.info("DTE_AUTO_EMAIL_RESULT dte_record_id=%s ok=%s", record.id, bool((result.get("results", {}).get("email") or {}).get("ok")))
        if "whatsapp" in channels:
            DTE_LOGGER.info("DTE_AUTO_WHATSAPP_RESULT dte_record_id=%s ok=%s", record.id, bool((result.get("results", {}).get("whatsapp") or {}).get("ok")))
    except Exception as exc:
        DTE_LOGGER.error("dte.auto_delivery.failed dte_id=%s order_id=%s error=%s", record.id, record.order_id, exc)


def _normalize_ambiente(raw_value: str | None) -> str:
    return normalize_ambiente(raw_value)


def _validate_ambiente_or_raise(raw_value: str | None, normalized: str) -> None:
    if normalized not in {"00", "01"}:
        raise DTEPreflightError(f"Ambiente inválido para DTE: {normalized}")


def _ambiente() -> str:
    configured_raw, source = resolve_ambiente_with_source()
    try:
        normalized = resolve_ambiente_from_env()
    except ValueError as exc:
        DTE_LOGGER.error("[DTE] ambiente_invalid source=%s raw=%s", source, configured_raw)
        raise DTEPreflightError(str(exc)) from exc
    _validate_ambiente_or_raise(None, normalized)
    DTE_LOGGER.info("[DTE] ambiente_resolved source=%s configured=%s resolved=%s", source, configured_raw, normalized)
    return normalized


def transmit_sale_dte(
    sale_id: int,
    source: str = "normal_send",
    force: bool = False,
    payment_id: int | None = None,
    queue_only: bool = False,
) -> DTERecord:
    DTE_LOGGER.info("[DTE] send_dte.start order=%s payment=%s source=%s", sale_id, payment_id, source)
    order = Order.objects.select_related("branch", "service_type", "customer").prefetch_related("items__applied_modifiers", "payments__payment_method").get(pk=sale_id)
    if order.dte_document_type != "CF":
        DTE_LOGGER.info("[DTE] send_dte.skip order=%s reason=unsupported_doc_type type=%s", sale_id, order.dte_document_type)
        raise DTEPreflightError(f"Tipo DTE aún no implementado: {order.dte_document_type}")
    dte_type = "CF_01"

    accepted = DTERecord.objects.filter(order=order, dte_type=dte_type, status=DTERecord.STATUS_ACCEPTED).first()
    if accepted and not force:
        DTE_LOGGER.info("[DTE] send_dte.return_existing order=%s dte_record=%s", sale_id, accepted.id)
        return accepted

    invoice, _ = OrderInvoice.objects.get_or_create(order=order)
    ambiente = _ambiente()
    codigo_generacion = build_generation_code(invoice.codigo_generacion)
    numero_control = invoice.numero_control or ""

    attempts = (invoice.dte_send_attempts or 0) + 1
    now = timezone.now()
    payment = order.payments.filter(id=payment_id).first() if payment_id else None

    payload: dict = {}
    active_branch = get_active_branch()
    record = DTERecord.objects.filter(order=order, dte_type=dte_type, credit_note__isnull=True).order_by("-id").first()

    try:
        numero_control = numero_control or next_control_number(order, dte_type=dte_type, ambiente=ambiente)
        DTE_LOGGER.info("[DTE] preflight.validating order=%s numero_control=%s ambiente=%s", sale_id, numero_control, ambiente)
        payload = build_payload_cf(order, control_number=numero_control, generation_code=codigo_generacion, ambiente=ambiente)
        DTE_LOGGER.info("Reservado correlativo CF: order=%s -> numeroControl=%s codigoGeneracion=%s", sale_id, numero_control, codigo_generacion)
    except DTEPreflightError as exc:
        DTE_LOGGER.info("[DTE] send_dte.preflight_failed order=%s error=%s", sale_id, exc)
        if not record:
            record = DTERecord(
                order=order,
                payment=payment,
                branch=active_branch,
                dte_type=dte_type,
            )
        parsed = {
            "status": DTERecord.STATUS_REJECTED,
            "hacienda_uuid": "",
            "sello_recepcion": "",
            "sello_recibido": "",
            "firma": "",
            "recibido_at": None,
            "estado_mh": "",
            "hacienda_state": "PRECHECK",
            "error_code": "PRECHECK",
            "error_message": str(exc),
        }
        response = {"success": False, "error": {"message": str(exc)}}
    else:
        if not record:
            record = DTERecord(
                order=order,
                payment=payment,
                branch=active_branch,
                dte_type=dte_type,
            )
        record.payment = payment
        record.branch = active_branch
        record.ambiente = ambiente
        record.control_number = numero_control
        record.generation_code = codigo_generacion
        record.codigo_generacion = codigo_generacion
        record.request_payload = {**payload, "branch": active_branch.name}
        record.receiver_name = (order.customer.name if order.customer_id else order.customer_name) or "Consumidor Final"
        record.issue_date = timezone.localdate()
        record.total_amount = order.total
        record.source = source
        record.attempts = attempts
        record.send_attempts = attempts
        record.last_sent_at = now
        record.status = DTERecord.STATUS_PENDING
        record.save()
        outbox = send_or_queue_dte(
            order=order,
            payment=payment,
            payload=payload,
            dte_record=record,
            attempt_immediate=not queue_only,
        )
        response = {}
        if outbox.response_body:
            try:
                response = json.loads(outbox.response_body)
            except Exception:
                response = {"raw": outbox.response_body}
        parsed = interpret_dte_response({**response, "http_status": outbox.response_status_code or 0, "response_text": outbox.response_body or ""})
        if outbox.status == "ACCEPTED":
            parsed["status"] = DTERecord.STATUS_ACCEPTED
        elif outbox.status == "REJECTED":
            parsed["status"] = DTERecord.STATUS_REJECTED
        elif outbox.status == "FAILED":
            parsed["status"] = DTERecord.STATUS_REJECTED
        elif outbox.status in {"PENDING", "SENT", "SENDING"}:
            parsed["status"] = DTERecord.STATUS_PENDING
        DTE_LOGGER.info(
            "[CF01] RECEIPT order=%s payment=%s estado=%s sello=%s firma=%s recibido_at=%s",
            sale_id,
            payment_id,
            parsed.get("estado_mh") or parsed.get("hacienda_state") or "",
            parsed.get("sello_recibido") or parsed.get("sello_recepcion") or "-",
            parsed.get("firma") or "-",
            parsed.get("recibido_at") or "-",
        )
        if parsed.get("status") in {DTERecord.STATUS_REJECTED}:
            DTE_LOGGER.error(
                "[DTE] rejection order=%s payment=%s code=%s message=%s ambiente=%s resumen=%s",
                sale_id,
                payment_id,
                parsed.get("error_code") or "",
                parsed.get("error_message") or "",
                ambiente,
                (payload.get("dte", {}).get("resumen", {}) if isinstance(payload, dict) else {}),
            )
    if not record:
        record = DTERecord(
            order=order,
            payment=payment,
            branch=active_branch,
            dte_type=dte_type,
        )
    record.payment = payment
    record.branch = active_branch
    record.ambiente = ambiente
    record.control_number = numero_control
    record.generation_code = codigo_generacion
    record.codigo_generacion = codigo_generacion
    record.status = parsed["status"]
    record.request_payload = {**payload, "branch": active_branch.name} if payload else (record.request_payload or {})
    record.response_payload = response if isinstance(response, dict) else {}
    record.response_text = parsed.get("response_text", "")
    record.mh_response_json = response if isinstance(response, dict) else {}
    record.mh_response_text = json.dumps(response, ensure_ascii=False, default=str) if isinstance(response, dict) else str(response)
    record.receiver_name = (order.customer.name if order.customer_id else order.customer_name) or "Consumidor Final"
    record.issue_date = timezone.localdate()
    record.total_amount = order.total
    record.source = source
    record.attempts = attempts
    record.send_attempts = attempts
    record.error_message = parsed["error_message"]
    record.error_code = parsed["error_code"]
    record.last_error_message = parsed["error_message"]
    record.last_error_code = parsed["error_code"]
    record.last_sent_at = now
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.sello_recibido = parsed.get("sello_recibido", parsed["sello_recepcion"])
    record.firma = parsed.get("firma", "")
    record.recibido_at = parsed.get("recibido_at")
    record.estado_mh = parsed.get("estado_mh", "")
    record.hacienda_state = parsed["hacienda_state"]
    record.hacienda_processed_at = parsed.get("recibido_at")
    record.save()

    invoice.status = "sent" if record.status == DTERecord.STATUS_ACCEPTED else "failed" if record.status == DTERecord.STATUS_REJECTED else "pending"
    invoice.dte_number = numero_control
    invoice.generation_code = codigo_generacion
    invoice.numero_control = numero_control
    invoice.codigo_generacion = codigo_generacion
    invoice.hacienda_payload = payload
    invoice.hacienda_response = response
    invoice.last_error = parsed["error_message"]
    invoice.dte_status = record.status
    invoice.dte_send_attempts = attempts
    invoice.last_dte_sent_at = now
    invoice.last_dte_error = parsed["error_message"]
    invoice.last_dte_error_code = parsed["error_code"]
    if record.status == DTERecord.STATUS_ACCEPTED:
        invoice.sent_at = now
    invoice.save()
    persist_sale_snapshot(order)
    if record.status == DTERecord.STATUS_ACCEPTED:
        _maybe_auto_send_delivery(record)
    DTE_LOGGER.info("[DTE] send_dte.done order=%s payment=%s record_status=%s", sale_id, payment_id, record.status)

    return record
