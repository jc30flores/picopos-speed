from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from apps.orders.models import Order
from apps.payments.models import Refund
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

    for fee in order.fees.all():
        fee_total = Decimal(fee.total_amount)
        name = f"{fee.quantity}x {fee.fee_name}"
        price = _format_money(fee_total)
        space = _width() - len(price) - 1
        lines.append(f"{name[:space].ljust(space)} {price}")

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

    for fee in order.fees.all():
        fee_total = Decimal(fee.total_amount)
        name = f"{fee.quantity}x {fee.fee_name}"
        price = _format_money(fee_total)
        space = _width() - len(price) - 1
        lines.append(f"{name[:space].ljust(space)} {price}")

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


def render_closeout_ticket(session, summary: dict) -> dict:
    now = timezone.localtime(session.closed_at or timezone.now())
    lines: list[str] = []
    lines.append(_line("Pico de Gallo POS"))
    lines.append(_line("Corte de caja"))
    lines.append(_divider())
    lines.append(_line(f"Register: {session.register.name}"))
    lines.append(_line(f"Opened: {timezone.localtime(session.opened_at).strftime('%Y-%m-%d %H:%M')}"))
    if session.closed_by:
        lines.append(_line(f"Closed by: {session.closed_by.username}"))
    lines.append(_line(f"Closed: {now.strftime('%Y-%m-%d %H:%M')}"))
    lines.append(_divider())
    lines.append(_line(f"Ventas brutas: {_format_money(summary['gross_total'])}"))
    lines.append(_line(f"Reembolsos: {_format_money(summary['refunds_total'])}"))
    lines.append(_line(f"Ventas netas: {_format_money(summary['net_sales_total'])}"))
    lines.append(_divider())
    lines.append(_line("Totales esperados"))
    lines.append(_line(f"Efectivo: {_format_money(summary['expected_cash'])}"))
    lines.append(_line(f"Tarjeta: {_format_money(summary['expected_card'])}"))
    lines.append(_line(f"Transferencia: {_format_money(summary['expected_transfer'])}"))
    lines.append(_line(f"Propinas: {_format_money(summary['expected_tips'])}"))
    lines.append(_divider())
    lines.append(_line("Reembolsos"))
    lines.append(_line(f"Efectivo: {_format_money(summary['refunds_cash'])}"))
    lines.append(_line(f"Tarjeta: {_format_money(summary['refunds_card'])}"))
    lines.append(_line(f"Transferencia: {_format_money(summary['refunds_transfer'])}"))
    lines.append(_line(f"Propinas: {_format_money(summary['refunds_tips'])}"))
    lines.append(_divider())
    lines.append(_line("Conteo final"))
    lines.append(_line(f"Efectivo: {_format_money(summary['counted_cash'])}"))
    lines.append(_line(f"Tarjeta: {_format_money(summary['counted_card'])}"))
    lines.append(_line(f"Transferencia: {_format_money(summary['counted_transfer'])}"))
    lines.append(_line(f"Propinas: {_format_money(summary['counted_tips'])}"))
    lines.append(_line(f"Sobre/Falta: {_format_money(summary['over_short_total'])}"))
    lines.append(_divider())
    lines.append(_line("Gracias"))

    text = "\n".join(lines)
    return {
        "text": text,
        "html": f"<pre>{text}</pre>",
        "meta": {
            "cash_session_id": session.id,
            "type": "closeout",
        },
    }


def render_refund_ticket(order: Order, refund: Refund) -> dict:
    now = timezone.localtime(refund.created_at)
    total_refund = refund.amount + refund.tip_refunded
    lines: list[str] = []
    lines.append(_line("Pico de Gallo POS"))
    lines.append(_line("Recibo de reembolso"))
    lines.append(_divider())
    lines.append(_line(f"Orden #{order.order_number}"))
    lines.append(_line(now.strftime("%Y-%m-%d %H:%M")))
    lines.append(_divider())
    lines.append(_line(f"Método: {refund.method}"))
    lines.append(_line(f"Monto: {_format_money(refund.amount)}"))
    if refund.tip_refunded > 0:
        lines.append(_line(f"Propina: {_format_money(refund.tip_refunded)}"))
    lines.append(_line(f"Total: {_format_money(total_refund)}"))
    lines.append(_divider())
    lines.append(_line(f"Motivo: {refund.reason}"))
    if refund.approved_by:
        lines.append(_line(f"Aprobado por: {refund.approved_by.username}"))
    if refund.original_payment and refund.original_payment.reference:
        lines.append(_line(f"Ref pago: {refund.original_payment.reference}"))
    lines.append(_divider())
    lines.append(_line("Articulos:"))
    for item in order.items.all():
        item_total = item.price_snapshot * item.quantity
        name = f"{item.quantity}x {item.product_name_snapshot}"
        price = _format_money(item_total)
        space = _width() - len(price) - 1
        lines.append(f"{name[:space].ljust(space)} {price}")
    lines.append(_divider())
    lines.append(_line("Fin del reembolso"))

    text = "\n".join(lines)
    return {
        "text": text,
        "html": f"<pre>{text}</pre>",
        "meta": {
            "order_id": order.id,
            "refund_id": refund.id,
            "type": "refund",
            "method": refund.method,
        },
    }


def render_void_ticket(order: Order, reason: str) -> dict:
    now = timezone.localtime(timezone.now())
    lines: list[str] = []
    lines.append(_line("Pico de Gallo POS"))
    lines.append(_line("Orden anulada"))
    lines.append(_divider())
    lines.append(_line(f"Orden #{order.order_number}"))
    lines.append(_line(now.strftime("%Y-%m-%d %H:%M")))
    lines.append(_divider())
    lines.append(_line(f"Motivo: {reason}"))
    lines.append(_divider())
    lines.append(_line("Articulos:"))
    for item in order.items.all():
        item_total = item.price_snapshot * item.quantity
        name = f"{item.quantity}x {item.product_name_snapshot}"
        price = _format_money(item_total)
        space = _width() - len(price) - 1
        lines.append(f"{name[:space].ljust(space)} {price}")
    lines.append(_divider())
    lines.append(_line("Fin de la anulacion"))

    text = "\n".join(lines)
    return {
        "text": text,
        "html": f"<pre>{text}</pre>",
        "meta": {
            "order_id": order.id,
            "type": "void",
            "reason": reason,
        },
    }
