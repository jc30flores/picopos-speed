from __future__ import annotations

from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.services.dte_service import interpret_dte_response, send_to_bridge


def resend_record(record: DTERecord) -> DTERecord:
    response = send_to_bridge(record.dte_type, record.request_payload)
    parsed = interpret_dte_response(response)

    record.response_payload = response
    record.status = parsed["status"]
    record.hacienda_state = parsed["hacienda_state"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.error_message = parsed["error_message"]
    record.error_code = parsed["error_code"]
    record.send_attempts += 1
    record.last_sent_at = timezone.now()
    record.save()
    return record
