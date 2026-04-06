from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order, OrderInvoice
from apps.dte.models import DTERecord
from apps.dte.services.active_branch import get_active_branch
from apps.dte.services.dte_factory import build_payload
from apps.dte.services.dte_numbers import next_control_number
from apps.dte.services.dte_parser import parse_hacienda_response
from apps.dte.services.dte_sender import send_payload


def transmit_invoice_dte(order_id: int, source: str = "normal_send") -> DTERecord:
    order = Order.objects.select_related("branch", "service_type").prefetch_related("items__applied_modifiers").get(id=order_id)
    active_branch = get_active_branch()

    accepted = DTERecord.objects.filter(order=order, dte_type="CF", status="aceptado").first()
    if accepted:
        return accepted

    invoice, _ = OrderInvoice.objects.get_or_create(order=order)
    control_number = invoice.numero_control or next_control_number(order, dte_type="CF")
    codigo = invoice.codigo_generacion or str(uuid.uuid4()).upper()

    payload = build_payload(order, control_number=control_number, codigo_generacion=codigo, dte_type="CF")
    attempts = (invoice.dte_send_attempts or 0) + 1

    with transaction.atomic():
        record = DTERecord.objects.create(
            order=order,
            branch=active_branch,
            dte_type="CF",
            status="enviando",
            control_number=control_number,
            codigo_generacion=codigo,
            request_payload=payload,
            receiver_name=order.customer_name or "Consumidor Final",
            issue_date=timezone.localdate(),
            total_amount=order.total,
            attempt_number=attempts,
            source=source,
        )

    try:
        response = send_payload(payload)
        parsed = parse_hacienda_response(response)
    except Exception as exc:
        response = {"ok": False, "error": str(exc), "status": "PENDIENTE"}
        parsed = {"status": "pendiente", "hacienda_state": "NETWORK_ERROR", "sello_recepcion": "", "hacienda_uuid": "", "error": str(exc), "error_code": "NETWORK"}

    record.response_payload = response
    record.status = parsed["status"]
    record.hacienda_state = parsed["hacienda_state"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.error_message = parsed["error"]
    record.error_code = parsed["error_code"]
    record.save()

    invoice.status = "sent" if record.status == "aceptado" else "failed" if record.status == "rechazado" else "pending"
    invoice.dte_number = control_number
    invoice.generation_code = codigo
    invoice.numero_control = control_number
    invoice.codigo_generacion = codigo
    invoice.hacienda_payload = payload
    invoice.hacienda_response = response
    invoice.last_error = parsed["error"]
    invoice.last_dte_error = parsed["error"]
    invoice.last_dte_error_code = parsed["error_code"]
    invoice.dte_send_attempts = attempts
    invoice.dte_status = record.status
    invoice.last_dte_sent_at = timezone.now()
    if record.status == "aceptado":
        invoice.sent_at = timezone.now()
    invoice.save()

    return record
