from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum

from apps.cashier.models import CashSession
from apps.cashier.services.reconciliation import calculate_session_payment_method_net
from apps.cashier.serializers import calculate_shift_summary
from apps.core.branch_profile import get_current_branch_id, get_branch_profile
from apps.core.models import Branch, ServiceType
from apps.orders.models import AppliedDiscount, Order
from apps.payments.models import Payment, Refund
from apps.payments.normalization import payment_code_from_payment
from apps.printing.receipt_pdf import build_receipt_pdf_from_text
from apps.printing.services.usb_printer import USBPrinterService

TZ_SV = ZoneInfo("America/El_Salvador")
TICKET_WIDTH = 39
INNER_WIDTH = 37
PREFIX = "  "
SEP_HYPHEN = f"{PREFIX}{'-' * INNER_WIDTH}"
SEP_DOTS = f"{PREFIX}{'.' * 36}"
SEP_UNDERSCORE = f"{PREFIX}{'_' * 36}"
SEP_TOTAL = f"{PREFIX}=========="
PAYMENT_METHOD_REPORT_ORDER = [
    ("cash", "EFECTIVO"),
    ("card", "TARJETA"),
    ("transfer", "TRANSFERENCIA"),
    ("paypal", "PAYPAL"),
    ("pedidos_ya", "PEDIDOS YA"),
]


def _as_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if not cleaned:
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _money(value: Decimal | float | int | str | None) -> str:
    return f"${_as_decimal(value):.2f}"


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
    base = Payment.objects.select_related("payment_method", "reporting_payment_method", "order")
    has_direct_session_rows = base.filter(cash_session=session).exists()
    if has_direct_session_rows:
        return base.filter(cash_session=session) | base.filter(
            cash_session__isnull=True,
            created_at__gte=start_at,
            created_at__lte=end_at,
        )
    return base.filter(created_at__gte=start_at, created_at__lte=end_at)


def _resolve_pdf_branch(session: CashSession):
    configured_branch_id = get_current_branch_id()
    if configured_branch_id:
        branch = Branch.objects.filter(id=configured_branch_id).first()
        if branch:
            return branch
    if getattr(session, "register", None) and session.register.branch_id:
        branch = Branch.objects.filter(id=session.register.branch_id).first()
        if branch:
            return branch
    return Branch.objects.order_by("id").first()


def _resolve_branch_profile(session: CashSession) -> dict[str, str]:
    resolved_branch = _resolve_pdf_branch(session)
    resolved_branch_id = getattr(resolved_branch, "id", None)
    profile = get_branch_profile(resolved_branch_id)
    if resolved_branch and not profile.get("branch_name"):
        profile["branch_name"] = resolved_branch.name
    if resolved_branch and not profile.get("branch_code"):
        profile["branch_code"] = resolved_branch.code
    return profile


def _payment_rows(session: CashSession):
    rows: list[str] = []
    total = Decimal("0")
    totals = {code: {"count": 0, "total": Decimal("0")} for code, _ in PAYMENT_METHOD_REPORT_ORDER}
    net = calculate_session_payment_method_net(session).totals_by_method
    for code in totals:
        totals[code]["total"] = Decimal(net.get(code) or 0)
    for payment in _payments_for_session(session):
        code = payment_code_from_payment(payment)
        if code in totals:
            totals[code]["count"] += 1
    for code, label in PAYMENT_METHOD_REPORT_ORDER:
        amount = Decimal(totals[code]["total"] or 0).quantize(Decimal("0.01"))
        count = int(totals[code]["count"] or 0)
        rows.append(_line_item(label, amount, count))
        total += amount
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


def _report_cash_lines(summary: dict, payments_qs, session: CashSession, branch: Branch | None = None):
    payment_map = {code: {"count": 0, "total": Decimal("0")} for code, _ in PAYMENT_METHOD_REPORT_ORDER}
    net = calculate_session_payment_method_net(session).totals_by_method
    for code in payment_map:
        payment_map[code]["total"] = Decimal(net.get(code) or 0)
    for payment in _payments_for_session(session):
        code = payment_code_from_payment(payment)
        if code in payment_map:
            payment_map[code]["count"] += 1

    cash_count = payment_map["cash"]["count"]
    cash_total = payment_map["cash"]["total"]

    register = getattr(session, "register", None)
    register_name = getattr(register, "name", "CAJA") or "CAJA"
    station_name = getattr(register, "station_name", "") or "POS 1"
    session_branch = getattr(getattr(register, "branch", None), "name", "")
    header_branch = (getattr(branch, "name", None) or session_branch or "SUCURSAL")

    return [
        header_branch.upper(),
        SEP_HYPHEN,
        "REPORTE DE CAJA",
        f"ESTACION {station_name} - {register_name}",
        _format_dt_sv(session.closed_at or timezone.now()),
        SEP_HYPHEN,
        _line_item("CANTIDAD INICIAL", _as_decimal(summary.get("opening_cash"))),
        SEP_DOTS,
        "Resumen De Pagos (+)",
        _line_item("EFECTIVO", cash_total, cash_count),
        SEP_DOTS,
        "OTHER TRANSACTIONS SUMMARY",
        "(DOES NOT AFFECT DRAWER COUNT)",
        _line_item("TARJETA", payment_map["card"]["total"], payment_map["card"]["count"]),
        "(CC TIPS NOT INCLUDED)",
        _line_item("TRANSFERENCIA", payment_map["transfer"]["total"], payment_map["transfer"]["count"]),
        _line_item("PAYPAL", payment_map["paypal"]["total"], payment_map["paypal"]["count"]),
        _line_item("PEDIDOS YA", payment_map["pedidos_ya"]["total"], payment_map["pedidos_ya"]["count"]),
        SEP_DOTS,
        _line_item("Efectivo En Caja", _as_decimal(summary.get("expected_cash_in_drawer"))),
        f"DRAWER RESET ID {session.id}",
        f"END OF DAY LOG ID {session.id}",
    ]


def build_end_of_day_ticket(session_id: int) -> str:
    session = CashSession.objects.select_related("register", "register__branch").get(pk=session_id)
    branch = _resolve_pdf_branch(session)
    branch_profile = _resolve_branch_profile(session)
    summary = calculate_shift_summary(session)
    ticket_timestamp = _format_dt_sv(session.closed_at or timezone.now())

    payments = _payments_for_session(session)
    order_ids = payments.values_list("order_id", flat=True).distinct()
    paid_orders = Order.objects.filter(id__in=order_ids).exclude(financial_status="voided")
    voided_orders = Order.objects.filter(id__in=order_ids, financial_status="voided")

    payment_rows, payment_total = _payment_rows(session)
    service_rows, service_total = _service_type_rows(paid_orders)
    item_rows, item_total = _item_subtotals(paid_orders)
    discount_rows, discount_total = _discount_rows(paid_orders)

    addr_1, addr_2, city_dept = _parse_branch_address(branch_profile.get("direccion_complemento", ""))

    lines: list[str] = [
        (branch_profile.get("emisor_nombre", "Pico de Gallo") or "Pico de Gallo").upper(),
        (branch_profile.get("branch_name", "") or getattr(branch, "name", "PICO DE GALLO POS") or "PICO DE GALLO POS").upper(),
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
        *_report_cash_lines(summary, payments, session, branch=branch),
    ]

    return "\n".join(lines)


def print_ticket_text(text: str) -> tuple[bool, str | None]:
    return USBPrinterService().print_text(text)


def _fallback_pdf_bytes(text: str) -> bytes:
    return build_receipt_pdf_from_text(text=text, filename="fallback.pdf").pdf_bytes


def build_end_of_day_ticket_pdf(session_id: int) -> bytes:
    session = CashSession.objects.select_related("register", "register__branch", "opened_by", "closed_by").get(pk=session_id)
    text = build_end_of_day_ticket(session_id)

    branch = _resolve_pdf_branch(session)
    profile = _resolve_branch_profile(session)
    branch_name = (profile.get("branch_name") or getattr(branch, "name", "") or "Sucursal").strip()
    branch_address = profile.get("direccion_complemento", "").strip()

    filename = f"end_of_day_{timezone.localtime(session.closed_at or timezone.now()).strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
    center_lines = ["Pico de Gallo POS", f"Sucursal {branch_name}"]
    if branch_address:
        center_lines.append(branch_address)

    return build_receipt_pdf_from_text(
        text=text,
        filename=filename,
        logo_path=str(Path(settings.BASE_DIR) / "assets" / "receipt" / "logo_pdg.png"),
        center_lines=center_lines,
    ).pdf_bytes
