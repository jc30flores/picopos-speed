from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from apps.cashier.models import CashSession
from apps.cashier.serializers import calculate_shift_summary
from apps.core.models import ServiceType
from apps.orders.models import AppliedDiscount, Order
from apps.payments.models import Payment, PaymentMethod, Refund
from apps.printing.services.usb_printer import USBPrinterService

TZ_SV = ZoneInfo("America/El_Salvador")
TICKET_WIDTH = 39
INNER_WIDTH = 37
PREFIX = "  "
SEP_HYPHEN = f"{PREFIX}{'-' * INNER_WIDTH}"
SEP_DOTS = f"{PREFIX}{'.' * 36}"
SEP_UNDERSCORE = f"{PREFIX}{'_' * 36}"
SEP_TOTAL = f"{PREFIX}=========="


def _money(value: Decimal | float | int | None) -> str:
    return f"${Decimal(value or 0):.2f}"


def _format_dt_sv(value) -> str:
    localized = timezone.localtime(value, TZ_SV)
    hour = localized.strftime("%I").lstrip("0") or "0"
    return f"{localized.strftime('%d/%m/%Y')} {hour}:{localized.strftime('%M:%S %p')}"


def _line_item(label: str, amount: Decimal, count: int | None = None) -> str:
    if count is None:
        return _row(label, _money(amount))
    return _row(f"{label}({int(count)})", _money(amount))


def _row(left: str, right: str) -> str:
    left = (left or "").strip()
    right = (right or "").strip()
    if not right:
        return f"{PREFIX}{left[:INNER_WIDTH]}"
    space = max(1, INNER_WIDTH - len(left) - len(right))
    return f"{PREFIX}{left[:INNER_WIDTH]}{' ' * space}{right}"


def _parse_branch_address(address: str) -> tuple[str, str, str]:
    parts = [piece.strip() for piece in (address or "").split(",") if piece.strip()]
    line_1 = parts[0] if len(parts) > 0 else ""
    line_2 = parts[1] if len(parts) > 1 else ""
    city_dept = ", ".join(parts[2:4]) if len(parts) > 2 else ""
    return line_1, line_2, city_dept


def _get_session_range(session: CashSession):
    start_at = session.opened_at
    end_at = session.closed_at or timezone.now()
    return start_at, end_at


def _payments_for_session(session: CashSession):
    start_at, end_at = _get_session_range(session)
    return Payment.objects.filter(created_at__gte=start_at, created_at__lte=end_at)


def _payment_rows(payments_qs):
    rows: list[str] = []
    total = Decimal("0")
    configured = list(PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name"))
    for method in configured:
        aggregate = payments_qs.filter(payment_method=method).aggregate(
            count=Count("id"),
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            ),
        )
        count = int(aggregate["count"] or 0)
        amount = Decimal(aggregate["total"] or 0)
        if count or amount:
            rows.append(_line_item(method.name.upper(), amount, count))
            total += amount

    if not rows:
        rows.append(_line_item("SIN PAGOS", Decimal("0"), 0))
    return rows, total


def _service_type_rows(orders_qs):
    rows: list[str] = []
    total = Decimal("0")
    configured = list(ServiceType.objects.filter(is_active=True).order_by("sort_order", "label"))
    for service_type in configured:
        aggregate = orders_qs.filter(service_type=service_type).aggregate(count=Count("id"), total=Sum("total"))
        count = int(aggregate["count"] or 0)
        amount = Decimal(aggregate["total"] or 0)
        if count or amount:
            rows.append(_line_item(service_type.label.upper(), amount, count))
            total += amount

    if not rows:
        rows.append(_line_item("SIN ORDENES", Decimal("0"), 0))
    return rows, total


def _item_subtotals(orders_qs):
    regular = Decimal("0")
    for row in orders_qs.values("items__price_snapshot", "items__quantity"):
        regular += Decimal(row.get("items__price_snapshot") or 0) * Decimal(row.get("items__quantity") or 0)

    modifiers = Decimal(
        orders_qs.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("items__applied_modifiers__modifier_price_snapshot") * F("items__quantity"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"]
        or 0
    )
    misc = Decimal(orders_qs.aggregate(total=Sum("disposable_total"))["total"] or 0)

    rows = [
        _line_item("REGULAR", regular),
        _line_item("REGULAR MODIFICADOR", modifiers),
        _line_item("MISC", misc),
    ]
    return rows, regular + modifiers + misc


def _discount_rows(orders_qs):
    discounts = AppliedDiscount.objects.filter(order__in=orders_qs)
    if not discounts.exists():
        return ["No discounts found"], Decimal("0")

    rows: list[str] = []
    total = Decimal("0")
    for row in discounts.values("discount_name_snapshot").annotate(count=Count("id"), total=Sum("amount_discounted")).order_by("discount_name_snapshot"):
        amount = Decimal(row["total"] or 0)
        total += amount
        rows.append(_line_item((row["discount_name_snapshot"] or "DISCOUNT").upper(), amount, int(row["count"] or 0)))
    return rows, total


def _refund_rows(session: CashSession):
    start_at, end_at = _get_session_range(session)
    refunds = Refund.objects.filter(created_at__gte=start_at, created_at__lte=end_at)
    if not refunds.exists():
        return ["NO REFUNDS FOUND"]

    rows: list[str] = []
    for row in refunds.values("method").annotate(count=Count("id"), total=Sum("amount")).order_by("method"):
        rows.append(_line_item((row["method"] or "refund").upper(), Decimal(row["total"] or 0), int(row["count"] or 0)))
    return rows


def _report_cash_lines(summary: dict, payments_qs, session: CashSession):
    def _method_total(code: str, fallback_method: str) -> tuple[int, Decimal]:
        aggregate = payments_qs.filter(payment_method__code=code).aggregate(
            count=Count("id"),
            total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2))),
        )
        count = int(aggregate["count"] or 0)
        total = Decimal(aggregate["total"] or 0)
        if count == 0 and total == 0:
            fallback = payments_qs.filter(payment_method__isnull=True, method=fallback_method).aggregate(
                count=Count("id"),
                total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2))),
            )
            return int(fallback["count"] or 0), Decimal(fallback["total"] or 0)
        return count, total

    cash_count, cash_total = _method_total("CASH", "cash")
    card_count, card_total = _method_total("CARD", "card")
    py_count, py_total = _method_total("PEDIDOS_YA", "transfer")

    station_name = session.register.station_name or "POS 1"
    return [
        session.register.branch.name.upper(),
        SEP_HYPHEN,
        "REPORTE DE CAJA",
        f"ESTACION {station_name} - {session.register.name}",
        _format_dt_sv(session.closed_at or timezone.now()),
        SEP_HYPHEN,
        _line_item("CANTIDAD INICIAL", Decimal(summary.get("opening_cash") or 0)),
        SEP_DOTS,
        "Resumen De Pagos (+)",
        _line_item("EFECTIVO", cash_total, cash_count),
        SEP_DOTS,
        "OTHER TRANSACTIONS SUMMARY",
        "(DOES NOT AFFECT DRAWER COUNT)",
        _line_item("T. CREDITO", card_total, card_count),
        "(CC TIPS NOT INCLUDED)",
        _line_item("PEDIDOS YA", py_total, py_count),
        SEP_DOTS,
        _line_item("Efectivo En Caja", Decimal(summary.get("expected_cash_in_drawer") or 0)),
        f"DRAWER RESET ID {session.id}",
        f"END OF DAY LOG ID {session.id}",
    ]


def build_end_of_day_ticket(session_id: int) -> str:
    session = CashSession.objects.select_related("register", "register__branch").get(pk=session_id)
    summary = calculate_shift_summary(session)
    ticket_timestamp = _format_dt_sv(session.closed_at or timezone.now())

    payments = _payments_for_session(session)
    order_ids = payments.values_list("order_id", flat=True).distinct()
    paid_orders = Order.objects.filter(id__in=order_ids).exclude(financial_status="voided")
    voided_orders = Order.objects.filter(id__in=order_ids, financial_status="voided")

    payment_rows, payment_total = _payment_rows(payments)
    service_rows, service_total = _service_type_rows(paid_orders)
    item_rows, item_total = _item_subtotals(paid_orders)
    discount_rows, discount_total = _discount_rows(paid_orders)

    addr_1, addr_2, city_dept = _parse_branch_address(session.register.branch.address)

    lines: list[str] = [
        session.register.branch.name.upper(),
        addr_1,
        addr_2,
        city_dept,
        SEP_HYPHEN,
        "Reporte De Cierre De Dia",
        ticket_timestamp,
        SEP_HYPHEN,
        SEP_HYPHEN,
        "Resumen De Pagos",
        SEP_HYPHEN,
        *payment_rows,
        SEP_TOTAL,
        _row("", _money(payment_total)),
        SEP_HYPHEN,
        "RESUMEN DE VENTAS POR TIPO DE ORDE",
        SEP_HYPHEN,
        *service_rows,
        SEP_TOTAL,
        _row("", _money(service_total)),
        SEP_HYPHEN,
        "SUBTOTAL POR TIPO DE ITEM",
        SEP_HYPHEN,
        *item_rows,
        SEP_TOTAL,
        _row("", _money(item_total)),
        SEP_HYPHEN,
        "RESUMEN DE VENTAS POR MESERO",
        SEP_HYPHEN,
        "SIN MESERO(0) $0.00",
        SEP_TOTAL,
        _row("", _money(Decimal("0"))),
        SEP_HYPHEN,
        "FIXED DISCOUNTS SUMMARY",
        SEP_HYPHEN,
        *discount_rows,
        SEP_TOTAL,
        _row("", _money(discount_total)),
        f"End Of Day Log Id {session.id}",
        SEP_UNDERSCORE,
        SEP_HYPHEN,
        "REPORTE ORDENES ANULADAS",
        "Ventas Actuales",
        ticket_timestamp,
        SEP_HYPHEN,
        "NO ANULACIONES ENCONTRADAS" if not voided_orders.exists() else f"ANULADAS({voided_orders.count()})",
        f"End Of Day Log Id {session.id}",
        SEP_UNDERSCORE,
        SEP_HYPHEN,
        "REPORTE PROPINAS OBLIGATORIAS",
        "Dia Actual",
        ticket_timestamp,
        SEP_HYPHEN,
        f"End Of Day Log Id {session.id}",
        SEP_UNDERSCORE,
        SEP_HYPHEN,
        "Descuentos De Item",
        "Dia Actual",
        ticket_timestamp,
        SEP_HYPHEN,
        "No Se Encontraron Descuentos de Linea" if not discount_rows or discount_rows == ["No discounts found"] else "DESCUENTOS DE LINEA APLICADOS",
        f"End Of Day Log Id {session.id}",
        SEP_UNDERSCORE,
        SEP_HYPHEN,
        "Cambios De Precio",
        "Dia Actual",
        ticket_timestamp,
        SEP_HYPHEN,
        "NO SE ENCUENTRAN CAMBIOS DE PRECIO",
        f"End Of Day Log Id {session.id}",
        SEP_UNDERSCORE,
        SEP_HYPHEN,
        "REEMBOLSOS",
        "Dia Actual",
        ticket_timestamp,
        SEP_HYPHEN,
        *_refund_rows(session),
        f"End Of Day Log Id {session.id}",
        SEP_UNDERSCORE,
        *_report_cash_lines(summary, payments, session),
    ]

    return "\n".join(lines)


def print_ticket_text(text: str) -> tuple[bool, str | None]:
    return USBPrinterService().print_text(text)


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
    for obj in objects:
        offsets.append(len(pdf.encode('latin-1')))
        pdf += obj + '\n'
    xref_offset = len(pdf.encode('latin-1'))
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    return pdf.encode('latin-1', errors='ignore')


def build_end_of_day_ticket_pdf(session_id: int) -> bytes:
    text = build_end_of_day_ticket(session_id)
    try:
        from io import BytesIO
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        lines = text.split("\n")
        page_width = 80 * mm
        left_margin = 4 * mm
        top_margin = 4 * mm
        line_height = 4.2 * mm
        page_height = max((len(lines) * line_height) + (top_margin * 2), 40 * mm)

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(page_width, page_height))
        c.setFont("Courier", 8.5)
        y = page_height - top_margin
        for line in lines:
            c.drawString(left_margin, y, line)
            y -= line_height
        c.save()
        return buf.getvalue()
    except Exception:
        return _fallback_pdf_bytes(text)
