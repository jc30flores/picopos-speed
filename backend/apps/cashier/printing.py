from __future__ import annotations

from django.utils import timezone

from apps.cashier.models import CashSession
from apps.cashier.serializers import calculate_shift_summary


def _line(text: str, width: int = 42) -> str:
    return (text or "")[:width]


def _divider(width: int = 37) -> str:
    return "-" * width


def _money(v) -> str:
    return f"${float(v or 0):.2f}"


def build_end_of_day_ticket(session_id: int) -> str:
    session = CashSession.objects.select_related("register", "register__branch", "opened_by", "closed_by").get(pk=session_id)
    summary = calculate_shift_summary(session)
    closed_at = timezone.localtime(session.closed_at or timezone.now())

    lines: list[str] = []
    lines.append(_line("PICO DE GALLO"))
    lines.append(_line(session.register.branch.address or ""))
    lines.append(_divider())
    lines.append(_line("Reporte De Cierre De Dia"))
    lines.append(_line(closed_at.strftime("%Y-%m-%d %H:%M")))
    lines.append(_divider())
    lines.append(_line("Resumen De Pagos"))
    lines.append(_line(f"EFECTIVO ({summary['payment_counts']['cash']}): {_money(summary['methods']['cash'])}"))
    lines.append(_line(f"TARJETA ({summary['payment_counts']['card']}): {_money(summary['methods']['card'])}"))
    lines.append(_line(f"TRANSFER ({summary['payment_counts']['transfer']}): {_money(summary['methods']['transfer'])}"))
    lines.append(_divider())
    lines.append(_line("Resumen de ventas por tipo de orden"))
    lines.append(_line("NO CLASIFICACION ENCONTRADA"))
    lines.append(_divider())
    lines.append(_line("Subtotal por tipo de item"))
    lines.append(_line("NO ITEMS ENCONTRADOS"))
    lines.append(_divider())
    lines.append(_line("Resumen por mesero"))
    lines.append(_line("NO MESEROS ENCONTRADOS"))
    lines.append(_divider())
    lines.append(_line("Anulaciones"))
    lines.append(_line("NO ANULACIONES ENCONTRADAS"))
    lines.append(_divider())
    lines.append(_line("Propinas obligatorias"))
    lines.append(_line("NO PROPINAS ENCONTRADAS"))
    lines.append(_divider())
    lines.append(_line("Descuentos de item"))
    lines.append(_line("NO DESCUENTOS ENCONTRADOS"))
    lines.append(_divider())
    lines.append(_line("Cambios de precio"))
    lines.append(_line("NO CAMBIOS ENCONTRADOS"))
    lines.append(_divider())
    lines.append(_line("Reembolsos"))
    lines.append(_line("NO REEMBOLSOS ENCONTRADOS"))
    lines.append(_divider())
    lines.append(_line("REPORTE DE CAJA"))
    lines.append(_line(f"Estacion/Caja: {session.register.station_name or session.register.name}"))
    lines.append(_line(f"Cantidad Inicial: {_money(summary['opening_cash'])}"))
    lines.append(_line(f"Resumen Efectivo (+): {_money(summary['total_cash_sales'])}"))
    lines.append(_line(f"Other Transactions Summary (-): {_money(summary['total_cash_out'])}"))
    lines.append(_line(f"Efectivo En Caja: {_money(summary['expected_cash_in_drawer'])}"))
    lines.append(_line(f"Contado: {_money(summary['counted_cash'])}"))
    lines.append(_line(f"Diferencia: {_money(summary['over_short_cash'])}"))
    lines.append(_divider())
    return "\n".join(lines)
