from __future__ import annotations

from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from apps.cashier.models import CashSession
from apps.cashier.serializers import calculate_shift_summary
from apps.core.models import ServiceType
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod


def _money(v) -> str:
    return f"${float(v or 0):.2f}"


def _lr(left: str, right: str, width: int = 42) -> str:
    left = str(left)
    right = str(right)
    space = max(1, width - len(left) - len(right))
    return f"{left}{' ' * space}{right}"


def _section_title(title: str, width: int = 42) -> list[str]:
    return ["-" * width, title, "-" * width]


def _build_payment_rows(payments_qs):
    configured = list(PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name"))
    rows = []
    total = Decimal("0")
    for method in configured:
        agg = payments_qs.filter(payment_method=method).aggregate(
            count=Count("id"),
            total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2))),
        )
        count = int(agg["count"] or 0)
        amount = agg["total"] or Decimal("0")
        if count or amount:
            rows.append((f"{method.name.upper()}({count})", amount))
            total += amount
    if not rows:
        rows.append(("SIN PAGOS(0)", Decimal("0")))
    return rows, total


def _build_service_type_rows(orders_qs):
    rows = []
    total = Decimal("0")
    configured = list(ServiceType.objects.filter(is_active=True).order_by("sort_order", "label"))
    for service_type in configured:
        agg = orders_qs.filter(service_type=service_type).aggregate(count=Count("id"), total=Sum("total"))
        count = int(agg["count"] or 0)
        amount = agg["total"] or Decimal("0")
        if count or amount:
            rows.append((f"{service_type.label.upper()}({count})", amount))
            total += amount
    if not rows:
        rows.append(("SIN ORDENES(0)", Decimal("0")))
    return rows, total


def _build_item_subtotals(orders_qs):
    items = orders_qs.values("items__price_snapshot", "items__quantity")
    base_items = Decimal("0")
    for row in items:
        price = row.get("items__price_snapshot") or Decimal("0")
        qty = row.get("items__quantity") or 0
        base_items += Decimal(price) * Decimal(qty)
    modifier_total = (
        orders_qs.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("items__applied_modifiers__modifier_price_snapshot") * F("items__quantity"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"]
        or Decimal("0")
    )
    return [("PRODUCTOS REGULARES", base_items), ("MODIFIERS", modifier_total)]


def _build_cashier_rows(payments_qs):
    rows = []
    for item in (
        payments_qs.values("received_by__username")
        .annotate(count=Count("id"), total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2))))
        .order_by("received_by__username")
    ):
        name = item["received_by__username"] or "SIN ASIGNAR"
        rows.append((f"{name.upper()}({int(item['count'] or 0)})", item["total"] or Decimal("0")))
    if not rows:
        rows.append(("SIN REGISTROS", Decimal("0")))
    return rows


def build_end_of_day_ticket(session_id: int) -> str:
    session = CashSession.objects.select_related("register", "register__branch").get(pk=session_id)
    summary = calculate_shift_summary(session)
    closed_at = timezone.localtime(session.closed_at or timezone.now())
    width = 42

    close_cutoff = session.closed_at or timezone.now()
    payments = Payment.objects.filter(created_at__gte=session.opened_at, created_at__lte=close_cutoff)
    order_ids = payments.values_list("order_id", flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids)

    payment_rows, payment_total = _build_payment_rows(payments)
    service_rows, service_total = _build_service_type_rows(orders)
    item_rows = _build_item_subtotals(orders)
    cashier_rows = _build_cashier_rows(payments)
    voided_count = orders.filter(financial_status="voided").count()

    lines: list[str] = []
    lines.extend([session.register.branch.name.upper(), session.register.branch.address or ""])
    lines.extend(_section_title("Reporte De Cierre De Dia", width))
    lines.append(_lr("Fecha", closed_at.strftime("%Y-%m-%d"), width))
    lines.append(_lr("Hora", closed_at.strftime("%H:%M:%S"), width))

    lines.extend(_section_title("Resumen De Pagos", width))
    for label, amount in payment_rows:
        lines.append(_lr(label, _money(amount), width))
    lines.append(_lr("TOTAL", _money(payment_total), width))

    lines.extend(_section_title("RESUMEN DE VENTAS POR TIPO DE ORDE", width))
    for label, amount in service_rows:
        lines.append(_lr(label, _money(amount), width))
    lines.append(_lr("TOTAL", _money(service_total), width))

    lines.extend(_section_title("SUBTOTAL POR TIPO DE ITEM", width))
    for label, amount in item_rows:
        lines.append(_lr(label, _money(amount), width))

    lines.extend(_section_title("RESUMEN DE VENTAS POR MESERO", width))
    for label, amount in cashier_rows:
        lines.append(_lr(label, _money(amount), width))

    lines.extend(_section_title("REPORTE ORDENES ANULADAS", width))
    lines.append("Sin anulaciones" if voided_count == 0 else _lr("Anuladas", str(voided_count), width))

    lines.extend(_section_title("REPORTE DE CAJA", width))
    lines.append(_lr("ESTACION", session.register.station_name or "POS", width))
    lines.append(_lr("CAJA", session.register.name, width))
    lines.append(_lr("CANTIDAD INICIAL", _money(summary["opening_cash"]), width))
    lines.append(_lr("EFECTIVO VENTAS", _money(summary["total_cash_sales"]), width))
    lines.append(_lr("GASTOS / PAGOS", _money(summary["cash_expenses_total"]), width))
    lines.append(_lr("EFECTIVO ESPERADO", _money(summary["expected_cash_in_drawer"]), width))
    lines.append(_lr("EFECTIVO CONTADO", _money(summary["counted_cash"]), width))
    lines.append(_lr("DIFERENCIA", _money(summary["difference"]), width))
    lines.extend(["-" * width, f"End Of Day Log Id {session.id}", "-" * width])
    return "\n".join(lines)


def print_ticket_text(text: str) -> tuple[bool, str | None]:
    if not getattr(settings, "PRINTER_ENABLED", False):
        return False, "Printer integration is disabled"
    if getattr(settings, "PRINTER_MODE", "usb").lower() != "usb":
        return False, "Unsupported PRINTER_MODE"
    required = {
        "PRINTER_USB_VENDOR_ID": settings.PRINTER_USB_VENDOR_ID,
        "PRINTER_USB_PRODUCT_ID": settings.PRINTER_USB_PRODUCT_ID,
        "PRINTER_USB_INTERFACE": settings.PRINTER_USB_INTERFACE,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        return False, f"Printer not configured. Missing: {', '.join(missing)}"
    try:
        import usb.core
        import usb.util
    except Exception:
        return False, "pyusb is not available"
    dev = usb.core.find(idVendor=int(settings.PRINTER_USB_VENDOR_ID), idProduct=int(settings.PRINTER_USB_PRODUCT_ID))
    if dev is None:
        return False, "Printer device not found"
    interface_number = int(settings.PRINTER_USB_INTERFACE)
    try:
        dev.set_configuration()
        cfg = dev.get_active_configuration()
        interface = usb.util.find_descriptor(cfg, bInterfaceNumber=interface_number)
        if interface is None:
            return False, f"Interface {interface_number} not found"
        out_ep = settings.PRINTER_USB_OUT_ENDPOINT
        if out_ep is None:
            bulk_out = usb.util.find_descriptor(
                interface,
                custom_match=lambda endpoint: usb.util.endpoint_direction(endpoint.bEndpointAddress) == usb.util.ENDPOINT_OUT
                and usb.util.endpoint_type(endpoint.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK,
            )
            if bulk_out is None:
                return False, "No BULK OUT endpoint found"
            out_ep = int(bulk_out.bEndpointAddress)
        dev.write(int(out_ep), (text + "\n\n\n").encode("utf-8"))
        dev.write(int(out_ep), b"\x1d\x56\x00")
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            usb.util.dispose_resources(dev)
        except Exception:
            pass


def _fallback_pdf_bytes(text: str) -> bytes:
    esc = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    content = f"BT /F1 10 Tf 40 760 Td ({esc.replace(chr(10), ') Tj T* (')}) Tj ET"
    objects = []
    objects.append('1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj')
    objects.append('2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj')
    objects.append('3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj')
    objects.append(f'4 0 obj << /Length {len(content)} >> stream\n{content}\nendstream endobj')
    objects.append('5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj')
    pdf = '%PDF-1.4\n'
    offsets = []
    for o in objects:
        offsets.append(len(pdf.encode('latin-1')))
        pdf += o + '\n'
    xref_offset = len(pdf.encode('latin-1'))
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    return pdf.encode('latin-1', errors='ignore')


def build_end_of_day_ticket_pdf(session_id: int) -> bytes:
    text = build_end_of_day_ticket(session_id)
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
        from io import BytesIO

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=LETTER)
        y = 760
        for line in text.split("\n"):
            c.drawString(40, y, line)
            y -= 14
            if y < 50:
                c.showPage()
                y = 760
        c.save()
        return buf.getvalue()
    except Exception:
        return _fallback_pdf_bytes(text)
