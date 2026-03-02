from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.services.builder import build_dte_payload
from apps.dte.services.client import send_to_bridge
from apps.dte.services.control import build_generation_code, next_control_number
from apps.dte.services.interpreter import interpret_response
from apps.orders.models import Order, OrderInvoice


def transmit_sale_dte(sale_id: int, source: str = "normal_send", force: bool = False) -> DTERecord:
    order = Order.objects.select_related("branch", "service_type").prefetch_related("items").get(pk=sale_id)
    accepted = DTERecord.objects.filter(order=order, dte_type="CF", status=DTERecord.STATUS_ACCEPTED).first()
    if accepted and not force:
        return accepted

    invoice, _ = OrderInvoice.objects.get_or_create(order=order)
    numero_control = invoice.numero_control or next_control_number(order, doc_type="CF")
    codigo_generacion = build_generation_code(invoice.codigo_generacion)
    attempts = (invoice.dte_send_attempts or 0) + 1

    payload = build_dte_payload(order, numero_control=numero_control, codigo_generacion=codigo_generacion, doc_type="CF")
    with transaction.atomic():
        record = DTERecord.objects.create(
            order=order,
            branch=order.branch,
            dte_type="CF",
            status=DTERecord.STATUS_SENDING,
            control_number=numero_control,
            codigo_generacion=codigo_generacion,
            request_payload=payload,
            response_payload={},
            receiver_name=order.customer_name or "Consumidor Final",
            issue_date=timezone.localdate(),
            total_amount=order.total,
            source=source,
            attempt_number=attempts,
            last_sent_at=timezone.now(),
        )

    response = send_to_bridge(payload)
    parsed = interpret_response(response)

    record.status = parsed["status"]
    record.hacienda_state = parsed["hacienda_state"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.error_message = parsed["error_message"]
    record.error_code = parsed["error_code"]
    record.response_payload = response
    record.last_sent_at = timezone.now()
    record.save()

    invoice.status = "sent" if record.status == DTERecord.STATUS_ACCEPTED else "pending" if record.status == DTERecord.STATUS_PENDING else "failed"
    invoice.dte_number = numero_control
    invoice.generation_code = codigo_generacion
    invoice.numero_control = numero_control
    invoice.codigo_generacion = codigo_generacion
    invoice.hacienda_payload = payload
    invoice.hacienda_response = response
    invoice.last_error = record.error_message
    invoice.dte_status = record.status
    invoice.dte_send_attempts = attempts
    invoice.last_dte_sent_at = record.last_sent_at
    invoice.last_dte_error = record.error_message
    invoice.last_dte_error_code = record.error_code
    if record.status == DTERecord.STATUS_ACCEPTED:
        invoice.sent_at = timezone.now()
    invoice.save()
    return record
