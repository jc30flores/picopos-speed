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
from apps.orders.models import Order, OrderInvoice
from apps.orders.services.snapshots import persist_sale_snapshot

DTE_LOGGER = logging.getLogger("apps.dte")


def _normalize_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _maybe_auto_send_email(record: DTERecord) -> None:
    flags = evaluate_record_actions(record)
    raw_email = str(flags.get("customer_email") or "").strip()
    normalized_email = _normalize_email(raw_email)
    DTE_LOGGER.info("dte.auto_email.check dte_id=%s order_id=%s", record.id, record.order_id)
    if not normalized_email:
        DTE_LOGGER.info("dte.auto_email.skip reason=empty_email dte_id=%s order_id=%s", record.id, record.order_id)
        return
    if normalized_email == INTERNAL_BILLING_EMAIL.strip().lower():
        DTE_LOGGER.info("dte.auto_email.skip reason=system_email dte_id=%s order_id=%s", record.id, record.order_id)
        return
    already_sent = DteDeliveryAttempt.objects.filter(
        dte_record=record,
        delivery_type=DteDeliveryAttempt.TYPE_EMAIL,
        status="SENT",
    ).exists()
    if already_sent:
        DTE_LOGGER.info("dte.auto_email.skip reason=already_sent dte_id=%s order_id=%s", record.id, record.order_id)
        return
    try:
        DTE_LOGGER.info("dte.auto_email.dispatch dte_id=%s order_id=%s", record.id, record.order_id)
        result = deliver_dte_to_client(record, channels=("email",), mode="automatic")
        email_result = (result.get("results") or {}).get("email") or {}
        if email_result.get("ok"):
            DTE_LOGGER.info("dte.auto_email.sent dte_id=%s order_id=%s", record.id, record.order_id)
        else:
            DTE_LOGGER.warning(
                "dte.auto_email.failed dte_id=%s order_id=%s error=%s",
                record.id,
                record.order_id,
                email_result.get("error") or result.get("summary"),
            )
    except Exception as exc:  # noqa: BLE001
        DTE_LOGGER.error("dte.auto_email.failed dte_id=%s order_id=%s error=%s", record.id, record.order_id, exc)


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
    prebuilt_record = DTERecord.objects.create(
        order=order,
        payment=payment,
        branch=active_branch,
        dte_type=dte_type,
        status=DTERecord.STATUS_PENDING,
        ambiente=ambiente,
        control_number=numero_control,
        generation_code=codigo_generacion,
        codigo_generacion=codigo_generacion,
        request_payload={},
        response_payload={},
        response_text="",
        mh_response_json={},
        mh_response_text="",
        receiver_name=(order.customer.name if order.customer_id else order.customer_name) or "Consumidor Final",
        issue_date=timezone.localdate(),
        total_amount=order.total,
        source=source,
        attempts=attempts,
        send_attempts=attempts,
        last_sent_at=now,
    )

    try:
        numero_control = numero_control or next_control_number(order, dte_type=dte_type, ambiente=ambiente)
        DTE_LOGGER.info("[DTE] preflight.validating order=%s numero_control=%s ambiente=%s", sale_id, numero_control, ambiente)
        build_payload_cf(order, control_number=numero_control, generation_code=codigo_generacion, ambiente=ambiente)
        DTE_LOGGER.info("Reservado correlativo CF: order=%s -> numeroControl=%s codigoGeneracion=%s", sale_id, numero_control, codigo_generacion)
        payload = build_payload_cf(order, control_number=numero_control, generation_code=codigo_generacion, ambiente=ambiente)
        prebuilt_record.request_payload = {**payload, "branch": active_branch.name}
        prebuilt_record.save(update_fields=["request_payload", "updated_at"])
    except DTEPreflightError as exc:
        DTE_LOGGER.info("[DTE] send_dte.preflight_failed order=%s error=%s", sale_id, exc)
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
        outbox = send_or_queue_dte(
            order=order,
            payment=payment,
            payload=payload,
            dte_record=prebuilt_record,
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
    prebuilt_record.status = parsed["status"]
    prebuilt_record.request_payload = {**payload, "branch": active_branch.name}
    prebuilt_record.response_payload = response if isinstance(response, dict) else {}
    prebuilt_record.response_text = parsed.get("response_text", "")
    prebuilt_record.mh_response_json = response if isinstance(response, dict) else {}
    prebuilt_record.mh_response_text = json.dumps(response, ensure_ascii=False, default=str) if isinstance(response, dict) else str(response)
    prebuilt_record.attempts = attempts
    prebuilt_record.send_attempts = attempts
    prebuilt_record.error_message = parsed["error_message"]
    prebuilt_record.error_code = parsed["error_code"]
    prebuilt_record.last_error_message = parsed["error_message"]
    prebuilt_record.last_error_code = parsed["error_code"]
    prebuilt_record.last_sent_at = now
    prebuilt_record.hacienda_uuid = parsed["hacienda_uuid"]
    prebuilt_record.sello_recepcion = parsed["sello_recepcion"]
    prebuilt_record.sello_recibido = parsed.get("sello_recibido", parsed["sello_recepcion"])
    prebuilt_record.firma = parsed.get("firma", "")
    prebuilt_record.recibido_at = parsed.get("recibido_at")
    prebuilt_record.estado_mh = parsed.get("estado_mh", "")
    prebuilt_record.hacienda_state = parsed["hacienda_state"]
    prebuilt_record.hacienda_processed_at = parsed.get("recibido_at")
    prebuilt_record.save()
    record = prebuilt_record

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
        _maybe_auto_send_email(record)
    DTE_LOGGER.info("[DTE] send_dte.done order=%s payment=%s record_status=%s", sale_id, payment_id, record.status)

    return record
