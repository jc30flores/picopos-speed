from __future__ import annotations

from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.services.dte_service import interpret_dte_response, send_to_bridge


def resend_record(record: DTERecord) -> DTERecord:
    response = send_to_bridge(
        record.dte_type,
        record.request_payload,
        branch_name=record.branch.name,
        order_id=record.order_id,
        branch_id=record.branch_id,
    )
    parsed = interpret_dte_response(response)

    record.response_payload = response
    record.response_text = parsed.get("response_text", "")
    record.status = parsed["status"]
    record.hacienda_state = parsed["hacienda_state"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.error_message = parsed["error_message"]
    record.error_code = parsed["error_code"]
    record.send_attempts += 1
    record.attempts = record.send_attempts
    record.last_error_code = record.error_code
    record.last_error_message = record.error_message
    record.last_sent_at = timezone.now()
    record.save()
    return record
