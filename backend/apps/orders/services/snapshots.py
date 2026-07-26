from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.dte.models import DTERecord
from apps.orders.models import Order, OrderInvoice
from apps.orders.services.totals import calculate_order_totals


def _money(value: Decimal) -> str:
    return f"{Decimal(value or 0):.2f}"


def build_sale_snapshot(order: Order) -> dict[str, Any]:
    customer = order.customer
    latest_payment = order.payments.select_related("payment_method").order_by("-id").first()
    latest_dte = DTERecord.objects.filter(order=order).order_by("-id").first()
    order_totals = calculate_order_totals(order)

    items = []
    for item in order.items.prefetch_related("applied_modifiers").all():
        modifiers = [
            {
                "name": mod.modifier_name_snapshot,
                "price": _money(mod.modifier_price_snapshot),
            }
            for mod in item.applied_modifiers.all()
        ]
        modifiers_total = sum((Decimal(mod["price"]) for mod in modifiers), Decimal("0"))
        unit_price = Decimal(item.effective_unit_price)
        quantity = Decimal(item.quantity)
        subtotal = (unit_price + modifiers_total) * quantity
        items.append(
            {
                "name": item.product_name_snapshot,
                "quantity": int(item.quantity),
                "unit_price": _money(item.effective_unit_price),
                "unit_price_override": _money(item.unit_price_override) if item.unit_price_override is not None else None,
                "subtotal": _money(subtotal),
                "discount_amount": _money(item.discount_amount),
                "code": item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}"),
                "is_custom": bool(item.is_custom),
                "modifiers": modifiers,
                "assigned_name": item.assigned_name,
            }
        )

    snapshot = {
        "order_id": order.id,
        "order_number": order.order_number,
        "created_at": order.created_at.isoformat(),
        "branch": {
            "id": order.branch_id,
            "name": order.branch.name,
            "code": order.branch.code,
        },
        "service_type": order.service_type.key if order.service_type else None,
        "channel": order.channel,
        "customer": {
            "id": customer.id if customer else None,
            "name": (customer.full_name or customer.name) if customer else (order.customer_name or "CONSUMIDOR FINAL"),
            "document": (customer.dui or customer.num_documento) if customer else None,
            "phone": customer.telefono if customer else None,
            "email": customer.correo if customer else None,
            "address": (customer.direccion or customer.direccion_complemento) if customer else None,
        },
        "items": items,
        "totals": {
            "subtotal": _money(order_totals.subtotal),
            "subtotal_after_discounts": _money(order_totals.subtotal_after_discounts),
            "iva": _money(order_totals.tax_total),
            "total": _money(order_totals.total),
            "discount_total": _money(order_totals.discount_total),
            "discount_snapshot": order.discount_snapshot or {},
            "disposable_total": _money(order_totals.disposable_total),
            "paid_total": _money(order_totals.paid_total),
            "amount_due": _money(order_totals.amount_due),
        },
        "payment": {
            "method": latest_payment.method if latest_payment else None,
            "method_code": latest_payment.payment_method.code if latest_payment and latest_payment.payment_method_id else None,
            "amount": _money(latest_payment.amount) if latest_payment else None,
            "tip_amount": _money(latest_payment.tip_amount) if latest_payment else None,
            "reference": latest_payment.reference if latest_payment else None,
            "payment_id": latest_payment.id if latest_payment else None,
        },
        "dte": {
            "record_id": latest_dte.id if latest_dte else None,
            "status": latest_dte.status if latest_dte else None,
            "request_payload": latest_dte.request_payload if latest_dte else {},
            "response_payload": latest_dte.response_payload if latest_dte else {},
        },
    }
    return snapshot


def persist_sale_snapshot(order: Order) -> OrderInvoice:
    invoice, _ = OrderInvoice.objects.get_or_create(order=order)
    invoice.sale_snapshot = build_sale_snapshot(order)
    invoice.save(update_fields=["sale_snapshot", "updated_at"])
    return invoice
