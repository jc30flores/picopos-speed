from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.outbox import send_or_queue_dte
from apps.dte.services.control import build_generation_code, next_control_number
from apps.dte.services.dte_service import DTEPreflightError, build_payload_cf
from apps.orders.models import OrderInvoice

LOGGER = logging.getLogger("apps.dte")


def _extract_payload_ident(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("dte", {}).get("identificacion", {}) if isinstance(payload, dict) else {}


def _payload_is_sendable(payload: dict[str, Any]) -> bool:
    if not isinstance(payload, dict) or not payload:
        return False
    dte = payload.get("dte")
    if not isinstance(dte, dict) or not dte:
        return False
    ident = dte.get("identificacion")
    cuerpo = dte.get("cuerpoDocumento")
    resumen = dte.get("resumen")
    if not isinstance(ident, dict):
        return False
    return bool(ident.get("numeroControl")) and bool(ident.get("codigoGeneracion")) and bool(cuerpo) and isinstance(resumen, dict)


def _resolve_resend_payload(record: DTERecord) -> tuple[dict[str, Any], str]:
    raw_payload = record.request_payload if isinstance(record.request_payload, dict) else {}
    if _payload_is_sendable(raw_payload):
        return raw_payload, "snapshot"

    invoice = OrderInvoice.objects.filter(order=record.order).first()
    ident = _extract_payload_ident(raw_payload)
    numero_control = (
        str(record.control_number or "").strip()
        or str(ident.get("numeroControl") or "").strip()
        or str(getattr(invoice, "numero_control", "") or "").strip()
    )
    codigo_generacion = (
        str(record.codigo_generacion or "").strip()
        or str(record.generation_code or "").strip()
        or str(ident.get("codigoGeneracion") or "").strip()
        or str(getattr(invoice, "codigo_generacion", "") or "").strip()
    )
    ambiente = str(record.ambiente or "00").strip() or "00"
    if not numero_control:
        numero_control = next_control_number(record.order, dte_type=record.dte_type or "CF_01", ambiente=ambiente)
    if not codigo_generacion:
        codigo_generacion = build_generation_code()

    rebuilt = build_payload_cf(
        record.order,
        control_number=numero_control,
        generation_code=codigo_generacion,
        ambiente=ambiente,
    )
    return rebuilt, "rebuild"


def resend_record(record: DTERecord) -> DTERecord:
    payment = record.order.payments.order_by("-id").first()
    invoice = OrderInvoice.objects.filter(order=record.order).first()
    initial_status = record.status
    payload_source = "snapshot"
    try:
        payload, payload_source = _resolve_resend_payload(record)
    except DTEPreflightError as exc:
        record.status = DTERecord.STATUS_REJECTED
        record.error_code = "PRECHECK"
        record.error_message = str(exc)
        record.last_error_code = "PRECHECK"
        record.last_error_message = str(exc)
        record.send_attempts = (record.send_attempts or 0) + 1
        record.attempts = record.send_attempts
        record.last_sent_at = timezone.now()
        record.save()
        LOGGER.error(
            "dte.resend.preflight_failed dte_record_id=%s order_id=%s payment_id=%s invoice_id=%s reason=%s",
            record.id,
            record.order_id,
            getattr(payment, "id", None),
            getattr(invoice, "id", None),
            exc,
        )
        return record

    ident = _extract_payload_ident(payload)
    numero_control = str(ident.get("numeroControl") or "").strip()
    codigo_generacion = str(ident.get("codigoGeneracion") or "").strip()
    if not numero_control or not codigo_generacion or not payload.get("dte"):
        reason = "Resend abortado: payload DTE inválido o incompleto (numeroControl/codigoGeneracion)."
        record.status = DTERecord.STATUS_REJECTED
        record.error_code = "PRECHECK"
        record.error_message = reason
        record.last_error_code = "PRECHECK"
        record.last_error_message = reason
        record.send_attempts = (record.send_attempts or 0) + 1
        record.attempts = record.send_attempts
        record.last_sent_at = timezone.now()
        record.save()
        LOGGER.error(
            "dte.resend.invalid_payload dte_record_id=%s order_id=%s payment_id=%s invoice_id=%s",
            record.id,
            record.order_id,
            getattr(payment, "id", None),
            getattr(invoice, "id", None),
        )
        return record

    LOGGER.info(
        "dte.resend.start dte_record_id=%s order_id=%s payment_id=%s invoice_id=%s numero_control=%s codigo_generacion=%s payload_source=%s payload_size=%s",
        record.id,
        record.order_id,
        getattr(payment, "id", None),
        getattr(invoice, "id", None),
        numero_control,
        codigo_generacion,
        payload_source,
        len(str(payload)),
    )

    record.control_number = numero_control
    record.generation_code = codigo_generacion
    record.codigo_generacion = codigo_generacion
    record.request_payload = payload
    record.save(update_fields=["control_number", "generation_code", "codigo_generacion", "request_payload", "updated_at"])

    if invoice:
        updates = []
        if invoice.numero_control != numero_control:
            invoice.numero_control = numero_control
            invoice.dte_number = numero_control
            updates.extend(["numero_control", "dte_number"])
        if invoice.codigo_generacion != codigo_generacion:
            invoice.codigo_generacion = codigo_generacion
            invoice.generation_code = codigo_generacion
            updates.extend(["codigo_generacion", "generation_code"])
        if updates:
            updates.append("updated_at")
            invoice.save(update_fields=updates)

    outbox = send_or_queue_dte(order=record.order, payment=payment, payload=payload, dte_record=record)
    record.refresh_from_db()
    LOGGER.info(
        "dte.resend.done dte_record_id=%s order_id=%s invoice_id=%s outbox_id=%s outbox_status=%s transition=%s->%s error=%s",
        record.id,
        record.order_id,
        getattr(invoice, "id", None),
        outbox.id,
        outbox.status,
        initial_status,
        record.status,
        record.error_message or "",
    )
    return record
