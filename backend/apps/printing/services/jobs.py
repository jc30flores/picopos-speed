from django.conf import settings
from apps.orders.models import Order
from apps.printing.models import PrintJob
from apps.printing.services.renderers import render_customer_ticket, render_kitchen_ticket


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
        meta=meta,
        requested_by=requested_by,
    )
    return job


def get_print_width() -> int:
    return getattr(settings, "PRINT_WIDTH", 42)
