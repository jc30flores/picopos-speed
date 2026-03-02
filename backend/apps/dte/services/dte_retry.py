from __future__ import annotations

from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.services.dte_sender import send_payload
from apps.dte.services.dte_parser import parse_hacienda_response


def resend_record(record: DTERecord) -> DTERecord:
    response = send_payload(record.request_payload)
    parsed = parse_hacienda_response(response)
    record.response_payload = response
    record.status = parsed["status"]
    record.hacienda_state = parsed["hacienda_state"]
    record.sello_recepcion = parsed["sello_recepcion"]
    record.hacienda_uuid = parsed["hacienda_uuid"]
    record.error_message = parsed["error"]
    record.error_code = parsed["error_code"]
    record.updated_at = timezone.now()
    record.save()
    return record
