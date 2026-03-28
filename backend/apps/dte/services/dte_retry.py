from __future__ import annotations

from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.outbox import send_or_queue_dte
from apps.dte.services.dte_service import interpret_dte_response


def resend_record(record: DTERecord) -> DTERecord:
    payment = record.order.payments.order_by("-id").first()
    outbox = send_or_queue_dte(order=record.order, payment=payment, payload=record.request_payload or {}, dte_record=record)
    response = {}
    if outbox.response_body:
        try:
            import json

            response = json.loads(outbox.response_body)
        except Exception:
            response = {"raw": outbox.response_body}
    response["http_status"] = outbox.response_status_code or 0
    parsed = interpret_dte_response(response)

    record.response_payload = response
    record.response_text = parsed.get("response_text", "")
    record.status = parsed["status"]
    record.hacienda_state = parsed["hacienda_state"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.error_message = parsed["error_message"]
    record.error_code = parsed["error_code"]
    record.send_attempts = max(record.send_attempts + 1, outbox.attempts)
    record.attempts = record.send_attempts
    record.last_error_code = record.error_code
    record.last_error_message = record.error_message
    record.last_sent_at = timezone.now()
    record.save()
    return record
