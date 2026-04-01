import json

from django.core.serializers.json import DjangoJSONEncoder
from django.conf import settings
from apps.orders.models import Order
from apps.printing.models import PrintJob
from apps.printing.services.renderers import (
    render_customer_ticket,
    render_kitchen_ticket,
    render_refund_ticket,
    render_void_ticket,
)


def json_safe(value):
    return json.loads(json.dumps(value, cls=DjangoJSONEncoder))


def create_print_job(order: Order, job_type: str, requested_by=None, event: str | None = None) -> PrintJob:
    renderer = render_kitchen_ticket if job_type == "kitchen" else render_customer_ticket
    payload = renderer(order)
    meta = payload.get("meta", {})
    if event:
        meta["event"] = event

    job = PrintJob.objects.create(
        order=order,
        type=job_type,
        status="rendered",
        content_text=payload["text"],
        content_html=payload.get("html", ""),
        meta=json_safe(meta),
        requested_by=requested_by,
    )
    return job


def get_print_width() -> int:
    return getattr(settings, "PRINT_WIDTH", 42)


def create_refund_print_job(refund, requested_by=None) -> PrintJob:
    payload = render_refund_ticket(refund.order, refund)
    return PrintJob.objects.create(
        order=refund.order,
        type="refund",
        status="rendered",
        content_text=payload["text"],
        content_html=payload.get("html", ""),
        meta=json_safe(payload.get("meta", {})),
        requested_by=requested_by,
    )


def create_void_print_job(order: Order, reason: str, requested_by=None) -> PrintJob:
    payload = render_void_ticket(order, reason)
    return PrintJob.objects.create(
        order=order,
        type="void",
        status="rendered",
        content_text=payload["text"],
        content_html=payload.get("html", ""),
        meta=json_safe(payload.get("meta", {})),
        requested_by=requested_by,
    )
