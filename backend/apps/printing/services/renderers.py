from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from apps.orders.models import Order
from apps.payments.models import Payment


def _width() -> int:
    return getattr(settings, "PRINT_WIDTH", 42)


def _line(text: str) -> str:
    width = _width()
    return text[:width].ljust(width)


def _format_money(value: Decimal) -> str:
    return f"${value:.2f}"


def _divider() -> str:
    return "-" * _width()


def render_kitchen_ticket(order: Order) -> dict:
    now = timezone.localtime(order.created_at)
    lines: list[str] = []
    lines.append(_line("Pico de Gallo POS"))
    lines.append(_line(order.branch.name if order.branch else "Sucursal"))
    lines.append(_divider())
    lines.append(_line(f"Orden #{order.order_number}"))
    lines.append(_line(now.strftime("%Y-%m-%d %H:%M")))
    lines.append(_line(f"Servicio: {order.service_type.key}"))
    lines.append(_divider())

    for item in order.items.all():
        item_total = item.price_snapshot * item.quantity
        name = f"{item.quantity}x {item.product_name_snapshot}"
        price = _format_money(item_total)
        space = _width() - len(price) - 1
        lines.append(f"{name[:space].ljust(space)} {price}")
        modifiers = item.applied_modifiers.all()
        for modifier in modifiers:
            mod_line = f"  - {modifier.modifier_name_snapshot}"
            lines.append(_line(mod_line))

    lines.append(_divider())
    lines.append(_line("Preparar con cuidado"))
    lines.append(_line("Gracias"))

    text = "\n".join(lines)
    return {
        "text": text,
        "html": f"<pre>{text}</pre>",
        "meta": {
            "order_id": order.id,
            "type": "kitchen",
            "service_type": order.service_type.key,
            "total_items": order.items.count(),
        },
    }


def render_customer_ticket(order: Order) -> dict:
    now = timezone.localtime(order.created_at)
    payments = Payment.objects.filter(order=order)
    total_paid = sum((payment.amount + payment.tip_amount for payment in payments), Decimal("0"))
    remaining = (order.total - total_paid).quantize(Decimal("0.01"))

    lines: list[str] = []
    lines.append(_line("Pico de Gallo POS"))
    lines.append(_line(order.branch.name if order.branch else "Sucursal"))
    lines.append(_divider())
    lines.append(_line(f"Orden #{order.order_number}"))
    lines.append(_line(now.strftime("%Y-%m-%d %H:%M")))
    lines.append(_line(f"Servicio: {order.service_type.key}"))
    lines.append(_divider())

    for item in order.items.all():
        item_total = item.price_snapshot * item.quantity
        name = f"{item.quantity}x {item.product_name_snapshot}"
        price = _format_money(item_total)
        space = _width() - len(price) - 1
        lines.append(f"{name[:space].ljust(space)} {price}")
        modifiers = item.applied_modifiers.all()
        for modifier in modifiers:
            mod_price = Decimal(modifier.modifier_price_snapshot)
            mod_line = f"  - {modifier.modifier_name_snapshot}"
            if mod_price > 0:
                price_text = _format_money(mod_price)
                space = _width() - len(price_text) - 1
                lines.append(f"{mod_line[:space].ljust(space)} {price_text}")
            else:
                lines.append(_line(mod_line))

    lines.append(_divider())
    lines.append(_line(f"Subtotal: {_format_money(order.subtotal)}"))
    lines.append(_line(f"Descuento: {_format_money(order.discount_total)}"))
    lines.append(_line(f"Impuesto (13%): {_format_money(order.tax)}"))
    lines.append(_line(f"Total: {_format_money(order.total)}"))
    lines.append(_divider())

    lines.append(_line("Pagos:"))
    for payment in payments:
        payment_total = payment.amount + payment.tip_amount
        lines.append(_line(f"- {payment.method}: {_format_money(payment_total)}"))
        if payment.tip_amount > 0:
            lines.append(_line(f"  Propina: {_format_money(payment.tip_amount)}"))
        if payment.reference:
            lines.append(_line(f"  Ref: {payment.reference}"))

    lines.append(_line(f"Pagado: {_format_money(total_paid)}"))
    lines.append(_line(f"Pendiente: {_format_money(remaining)}"))
    lines.append(_divider())
    lines.append(_line("Gracias por su visita"))

    text = "\n".join(lines)
    return {
        "text": text,
        "html": f"<pre>{text}</pre>",
        "meta": {
            "order_id": order.id,
            "type": "customer",
            "payment_status": order.payment_status,
            "total_paid": str(total_paid),
            "remaining": str(remaining),
        },
    }
