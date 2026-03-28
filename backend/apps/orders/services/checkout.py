from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from django.utils import timezone

from apps.orders.models import Order, OrderInvoice


@dataclass
class CheckoutResult:
    order_id: int
    invoice_id: int
    kitchen_routing: bool
    hacienda_status: str


def _build_dte_payload(order: Order) -> dict[str, Any]:
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "channel": order.channel,
        "total": str(order.total),
        "items": [
            {
                "name": item.product_name_snapshot,
                "code": item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}"),
                "is_custom": item.is_custom,
                "quantity": item.quantity,
                "price": str(item.price_snapshot),
                "modifiers": [
                    {
                        "name": mod.modifier_name_snapshot,
                        "price": str(mod.modifier_price_snapshot),
                    }
                    for mod in item.applied_modifiers.all()
                ],
            }
            for item in order.items.prefetch_related("applied_modifiers").all()
        ],
    }


def send_dte_to_hacienda(payload: dict[str, Any]) -> dict[str, Any]:
    """Stub for Hacienda integration. Replace with real API adapter."""
    now = timezone.localtime(timezone.now()).strftime("%Y%m%d%H%M%S")
    return {
        "ok": True,
        "status": "SENT",
        "dte_number": f"DTE-{payload['order_number']}-{now}",
        "generation_code": f"GEN-{payload['order_id']}-{now}",
        "provider_response": {"accepted": True, "timestamp": now},
    }


def create_order_and_invoice(order: Order) -> CheckoutResult:
    invoice, _ = OrderInvoice.objects.get_or_create(order=order)
    payload = _build_dte_payload(order)
    invoice.hacienda_payload = payload
    try:
        response = send_dte_to_hacienda(payload)
        if response.get("ok"):
            invoice.status = "sent"
            invoice.dte_number = response.get("dte_number", "")
            invoice.generation_code = response.get("generation_code", "")
            invoice.sent_at = timezone.now()
            invoice.last_error = ""
        else:
            invoice.status = "failed"
            invoice.last_error = response.get("error", "Unknown Hacienda error")
        invoice.hacienda_response = response
    except Exception as exc:
        invoice.status = "failed"
        invoice.last_error = str(exc)
        invoice.hacienda_response = {"ok": False, "error": str(exc)}
    invoice.save()

    return CheckoutResult(
        order_id=order.id,
        invoice_id=invoice.id,
        kitchen_routing=order.requires_kitchen,
        hacienda_status=invoice.status,
    )
