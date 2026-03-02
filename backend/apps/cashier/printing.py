from __future__ import annotations

from django.utils import timezone

from apps.cashier.models import CashSession
from apps.cashier.serializers import calculate_shift_summary


def _money(v) -> str:
    return f"${float(v or 0):.2f}"


def build_end_of_day_ticket(session_id: int) -> str:
    session = CashSession.objects.select_related("register", "register__branch").get(pk=session_id)
    summary = calculate_shift_summary(session)
    closed_at = timezone.localtime(session.closed_at or timezone.now())

    m = summary.get("methods", {})
    cash = m.get("CASH", {"count": 0, "total": 0})
    card = m.get("CARD", {"count": 0, "total": 0})
    transfer = m.get("TRANSFER", {"count": 0, "total": 0})
    pedidos = m.get("PEDIDOS_YA", {"count": 0, "total": 0})
    paypal = m.get("PAYPAL", {"count": 0, "total": 0})

    return "\n".join([
        "PICO DE GALLO",
        session.register.branch.address or "",
        "-------------------------------------",
        "Reporte De Cierre De Dia",
        closed_at.strftime("%Y-%m-%d %H:%M"),
        "-------------------------------------",
        "Resumen De Pagos",
        f"EFECTIVO({cash['count']}): {_money(cash['total'])}",
        f"TARJETA({card['count']}): {_money(card['total'])}",
        f"TRANSFERENCIA({transfer['count']}): {_money(transfer['total'])}",
        f"PEDIDOS YA({pedidos['count']}): {_money(pedidos['total'])}",
        f"PAYPAL({paypal['count']}): {_money(paypal['total'])}",
        "-------------------------------------",
        "REPORTE DE CAJA",
        f"ESTACION {session.register.station_name or 'POS'} - CAJA {session.register.name}",
        f"CANTIDAD INICIAL: {_money(summary['opening_cash'])}",
        f"Resumen de Pagos (+) EFECTIVO: {_money(summary['total_cash_sales'])}",
        "OTHER TRANSACTIONS SUMMARY (DOES NOT AFFECT DRAWER COUNT)",
        f"TARJETA: {_money(card['total'])}",
        f"TRANSFERENCIA: {_money(transfer['total'])}",
        f"PEDIDOS YA: {_money(pedidos['total'])}",
        f"PAYPAL: {_money(paypal['total'])}",
        f"GASTOS / PAGOS (SALIDAS): {_money(summary['cash_expenses_total'])}",
        f"Efectivo en caja (Esperado): {_money(summary['expected_cash_in_drawer'])}",
        f"Efectivo contado: {_money(summary['counted_cash'])}",
        f"Diferencia: {_money(summary['difference'])}",
        f"Cash Session ID: {session.id}",
        "Drawer Reset ID: —",
        "-------------------------------------",
    ])


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
