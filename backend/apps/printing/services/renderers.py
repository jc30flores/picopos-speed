from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from textwrap import wrap
from django.conf import settings
from django.utils import timezone
from apps.core.branch_profile import get_branch_profile
from apps.dte.models import DTERecord
from apps.dte.services.hacienda import build_hacienda_consulta_publica_url
from apps.dte.services.payment_methods import get_cat017_code_and_label
from apps.orders.models import Order
from apps.payments.models import Refund


def _width() -> int:
    return getattr(settings, "PRINT_WIDTH", 42)


def _line(text: str) -> str:
    width = _width()
    return text[:width].ljust(width)


def _center(text: str) -> str:
    width = _width()
    raw = (text or "")[:width]
    return raw.center(width)


def _format_money(value: Decimal) -> str:
    normalized = Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"${normalized:.2f}"


def _divider() -> str:
    return "-" * _width()


def _service_type_label(order: Order) -> str:
    key = str(order.service_type.key if order.service_type else "sin_tipo").strip().lower()
    mapping = {
        "dinein": "DINE IN",
        "dine_in": "DINE IN",
        "takeout": "TAKEOUT",
        "pickup": "PICKUP",
        "delivery": "DELIVERY",
        "drive_thru": "DRIVE THRU",
    }
    return mapping.get(key, key.replace("_", " ").upper())


def _display_brand_name(value: str) -> str:
    raw = str(value or "").strip()
    if raw.lower().startswith("pico de gallo"):
        return "GastroPOSV"
    return raw or "GastroPOSV"


def _format_right_label_value(label: str, value: str) -> str:
    text = f"{label}:"
    space = _width() - len(text) - len(value) - 1
    if space < 1:
        return _line(f"{text} {value}")
    return f"{text}{' ' * space} {value}"


def _logo_path() -> Path | None:
    try:
        from apps.core.ticket_settings import get_ticket_logo_path

        configured = get_ticket_logo_path()
    except Exception:
        configured = None
    return Path(configured) if configured else None


def _normalize_dte_status(raw_status: str | None, *, has_dte: bool) -> str:
    text = str(raw_status or "").strip().upper()
    if not has_dte:
        return "SIN DTE"
    if text in {"ACEPTADO", "PROCESADO", "RECIBIDO", "OK"}:
        return "ACEPTADO"
    if text in {"RECHAZADO", "FAILED", "ERROR", "INVALIDO", "INVÁLIDO"}:
        return "RECHAZADO"
    if text in {"INVALIDADO", "ANULADO"}:
        return "INVALIDADO"
    return "PENDIENTE"


def _qr_value(ctx: dict) -> str:
    dte = ctx.get("dte") or {}
    totals = ctx.get("totals") or {}
    codigo = str(dte.get("codigo_generacion") or "").strip()
    numero = str(dte.get("numero_control") or "").strip()
    fecha = str(dte.get("fecha_dte") or ctx.get("order_datetime") or "").strip()
    total = str(totals.get("total") or "").strip()
    estado = str(dte.get("estado_dte") or "").strip()
    sello = str(dte.get("sello_recibido") or "").strip()
    if codigo or numero:
        return " | ".join(
            part
            for part in [
                f"CG:{codigo}" if codigo else "",
                f"NC:{numero}" if numero else "",
                f"FECHA:{fecha}" if fecha else "",
                f"TOTAL:{total}" if total else "",
                f"ESTADO:{estado}" if estado else "",
                f"SELLO:{sello}" if sello else "",
            ]
            if part
        )
    return " | ".join(part for part in [f"ORDEN:{ctx.get('order_number') or '-'}", f"FECHA:{fecha}" if fecha else "", f"TOTAL:{total}" if total else "", "ESTADO:SIN DTE"] if part)


def _display_payment_label(payment) -> str:
    if payment is None:
        return "Efectivo"
    payment_method = getattr(payment, "payment_method", None)
    method_code = str(getattr(payment_method, "code", "") or "").strip().lower().replace("-", "_")
    method_name = str(getattr(payment_method, "name", "") or "").strip()
    if method_code == "pedidos_ya":
        return "Pedidos Ya"
    if method_name:
        return method_name
    _, label = get_cat017_code_and_label(payment)
    return label


def _derive_totals_from_total(total_including_iva: Decimal) -> tuple[Decimal, Decimal]:
    total = Decimal(str(total_including_iva or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    iva_rate = Decimal("0.13")
    subtotal = (total / (Decimal("1.00") + iva_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    iva = (total - subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # Ensure exact identity subtotal + iva == total
    if subtotal + iva != total:
        iva = (total - subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return subtotal, iva


def _format_item_row(*, qty: int | float | Decimal, desc: str, unit: Decimal, total: Decimal, col_qty: int, col_desc: int, col_unit: int, col_total: int) -> list[str]:
    wrapped_desc = wrap(str(desc or ""), width=col_desc, break_long_words=True, break_on_hyphens=False) or [""]
    lines = [
        f"{str(qty)[:col_qty]:<{col_qty}} {wrapped_desc[0]:<{col_desc}} {_format_money(unit):>{col_unit}} {_format_money(total):>{col_total}}"
    ]
    indent = " " * (col_qty + 1)
    for extra_line in wrapped_desc[1:]:
        lines.append(f"{indent}{extra_line:<{col_desc}} {'':>{col_unit}} {'':>{col_total}}")
    return lines


def build_receipt_context(order: Order) -> dict:
    branch_profile = get_branch_profile(getattr(order, "branch_id", None))
    payments = list(order.payments.select_related("payment_method", "received_by").order_by("-id"))
    main_payment = payments[0] if payments else None
    amount_paid = sum((p.amount + p.tip_amount for p in payments), Decimal("0")).quantize(Decimal("0.01"))
    change_due = Decimal("0.00")
    if main_payment and main_payment.cash_received:
        change_due = max(Decimal(main_payment.cash_received) - (main_payment.amount + main_payment.tip_amount), Decimal("0.00")).quantize(Decimal("0.01"))

    cat017_code, _ = get_cat017_code_and_label(main_payment)
    method_label = _display_payment_label(main_payment)
    cashier_name = "-"
    if main_payment and main_payment.received_by:
        cashier_name = main_payment.received_by.get_full_name() or main_payment.received_by.username

    dte_record = DTERecord.objects.filter(order=order).order_by("-id").first()
    dte_payload = (dte_record.request_payload or {}).get("dte", {}) if dte_record else {}
    identificacion = dte_payload.get("identificacion", {}) if isinstance(dte_payload, dict) else {}
    resumen = dte_payload.get("resumen", {}) if isinstance(dte_payload, dict) else {}
    fecha_dte = identificacion.get("fecEmi") if isinstance(identificacion, dict) else ""
    codigo_generacion = (identificacion.get("codigoGeneracion") if isinstance(identificacion, dict) else "") or (dte_record.codigo_generacion if dte_record else "")
    numero_control = (identificacion.get("numeroControl") if isinstance(identificacion, dict) else "") or (dte_record.control_number if dte_record else "")
    response_payload = dte_record.response_payload if dte_record and isinstance(dte_record.response_payload, dict) else {}
    respuesta_hacienda = response_payload.get("respuesta_hacienda") if isinstance(response_payload.get("respuesta_hacienda"), dict) else {}
    estado_raw = (
        (dte_record.status if dte_record else "")
        or str(response_payload.get("status") or "").strip()
        or str(response_payload.get("estado") or "").strip()
        or str(respuesta_hacienda.get("estado") or "").strip()
        or str(dte_record.estado_mh if dte_record else "").strip()
        or str(dte_record.hacienda_state if dte_record else "").strip()
    )
    estado_dte = _normalize_dte_status(estado_raw, has_dte=bool(dte_record))
    sello_recibido = (
        (dte_record.sello_recibido if dte_record else "")
        or (dte_record.sello_recepcion if dte_record else "")
        or str(response_payload.get("sello_recibido") or "").strip()
        or str(respuesta_hacienda.get("selloRecibido") or "").strip()
    )
    fh_procesamiento = (
        str(response_payload.get("fhProcesamiento") or "").strip()
        or str(response_payload.get("fh_procesamiento") or "").strip()
        or str(respuesta_hacienda.get("fhProcesamiento") or "").strip()
        or str(respuesta_hacienda.get("fh_procesamiento") or "").strip()
        or (timezone.localtime(dte_record.hacienda_processed_at).isoformat() if dte_record and dte_record.hacienda_processed_at else "")
        or (timezone.localtime(dte_record.recibido_at).isoformat() if dte_record and dte_record.recibido_at else "")
    )

    payment_total = sum((Decimal(str(p.amount or "0")) for p in payments), Decimal("0"))
    total_source = payment_total if payment_total > 0 else Decimal(str(resumen.get("totalPagar") or order.total or "0.00"))
    total = Decimal(str(total_source)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    subtotal_display, iva_display = _derive_totals_from_total(total)
    iva = iva_display
    iva_rete1 = Decimal(str(resumen.get("ivaRete1") or "0.00")).quantize(Decimal("0.01"))

    items: list[dict] = []
    for item in order.items.all().prefetch_related("applied_modifiers"):
        unit_price = Decimal(item.effective_unit_price).quantize(Decimal("0.01"))
        line_total = (unit_price * item.quantity).quantize(Decimal("0.01"))
        items.append({"qty": item.quantity, "name": item.product_name_snapshot, "unit_price": unit_price, "line_total": line_total})
        for mod in item.applied_modifiers.all():
            mod_price = Decimal(mod.modifier_price_snapshot or 0).quantize(Decimal("0.01"))
            if mod_price > 0:
                items.append({"qty": 1, "name": f"+ {mod.modifier_name_snapshot}", "unit_price": mod_price, "line_total": mod_price})

    disposable_total = Decimal("0.00")
    for fee in order.fees.all():
        fee_total = Decimal(fee.total_amount).quantize(Decimal("0.01"))
        fee_type = str(getattr(fee, "fee_type", "") or "").strip().lower()
        fee_name = str(getattr(fee, "fee_name", "") or "").strip()
        if fee_type == "disposable" or fee_name.lower() == "desechables":
            disposable_total += fee_total
            continue
        items.append({"qty": int(fee.quantity), "name": fee.fee_name, "unit_price": Decimal(fee.unit_amount).quantize(Decimal("0.01")), "line_total": fee_total})
    if disposable_total > 0:
        disposable_total = disposable_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        items.append({"qty": 1, "name": "Desechables", "unit_price": disposable_total, "line_total": disposable_total})

    public_url = build_hacienda_consulta_publica_url(fecha_dte, codigo_generacion)
    logo_path = _logo_path()
    return {
        "restaurant_name": branch_profile.get("branch_name") or (order.branch.name if order.branch else "GastroPOSV"),
        "tagline": branch_profile.get("emisor_nombre_comercial") or branch_profile.get("emisor_nombre") or "GastroPOSV",
        "address": branch_profile.get("direccion_complemento") or "",
        "phone": getattr(order.branch, "phone", "") or "",
        "service_type_label": _service_type_label(order),
        "cashier_name": cashier_name,
        "order_number": order.order_number,
        "order_datetime": timezone.localtime(order.created_at),
        "items": items,
        "totals": {
            "subtotal": subtotal_display,
            "iva": iva,
            "iva_rete1": iva_rete1,
            "total": total,
        },
        "payment": {
            "method_label_es": method_label,
            "method_code_cat017": cat017_code,
            "amount_paid": amount_paid,
            "change_due": change_due,
            "reference": (main_payment.reference if main_payment else "") or "",
        },
        "dte": {
            "estado_dte": estado_dte,
            "numero_control": numero_control,
            "codigo_generacion": codigo_generacion,
            "fecha_dte": fecha_dte or "",
            "sello_recibido": sello_recibido or "",
            "fh_procesamiento": fh_procesamiento or "",
        },
        "public_url": public_url,
        "qr_value": "",
        "logo_path": str(logo_path) if logo_path else "",
        "logo_exists": bool(logo_path and logo_path.exists()),
    }


def render_kitchen_ticket(order: Order) -> dict:
    now = timezone.localtime(order.created_at)
    lines: list[str] = []
    lines.append(_line("GastroPOSV"))
    lines.append(_line(order.branch.name if order.branch else "Sucursal"))
    lines.append(_divider())
    lines.append(_line(f"Orden #{order.order_number}"))
    lines.append(_line(now.strftime("%Y-%m-%d %H:%M")))
    lines.append(_line(f"Servicio: {order.service_type.key if order.service_type else 'SIN_TIPO'}"))
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
            "service_type": (order.service_type.key if order.service_type else "SIN_TIPO"),
            "total_items": order.items.count(),
        },
    }


def render_customer_ticket(order: Order) -> dict:
    ctx = build_receipt_context(order)
    ctx["qr_value"] = _qr_value(ctx)
    col_qty = 3
    col_unit = 8
    col_total = 9
    col_desc = max(8, _width() - col_qty - col_unit - col_total - 3)
    brand_name = _display_brand_name(ctx["tagline"] or ctx["restaurant_name"])
    center_lines: list[str] = [brand_name]
    if ctx["address"]:
        center_lines.extend(wrap(str(ctx["address"]), width=_width()) or [str(ctx["address"])])
    center_lines.extend(
        [
            f"No. Control: {ctx['dte']['numero_control'] or '-'}",
            f"Codigo Gen: {ctx['dte']['codigo_generacion'] or '-'}",
            f"Sello Recibido: {ctx['dte'].get('sello_recibido') or '-'}",
        ]
    )

    lines: list[str] = [_center(line) for line in center_lines]
    lines.append(_divider())
    lines.append(_center(ctx["service_type_label"]))
    lines.append(_center(f"Orden #{ctx['order_number']}"))
    lines.append(_center(ctx["order_datetime"].strftime("%Y-%m-%d %H:%M")))
    lines.append(_divider())
    lines.append(f"{'CANT':<{col_qty}} {'DESCRIPCION':<{col_desc}} {'P.UNIT':>{col_unit}} {'TOTAL':>{col_total}}")
    lines.append(_divider())
    for item in ctx["items"]:
        lines.extend(
            _format_item_row(
                qty=item["qty"],
                desc=item["name"],
                unit=Decimal(str(item["unit_price"])),
                total=Decimal(str(item["line_total"])),
                col_qty=col_qty,
                col_desc=col_desc,
                col_unit=col_unit,
                col_total=col_total,
            )
        )

    lines.append(_divider())
    lines.append(_format_right_label_value("Subtotal", _format_money(ctx["totals"]["subtotal"])))
    lines.append(_format_right_label_value("IVA", _format_money(ctx["totals"]["iva"])))
    if ctx["totals"]["iva_rete1"] > 0:
        lines.append(_format_right_label_value("IVA Retenido 1%", _format_money(ctx["totals"]["iva_rete1"])))
    lines.append(_format_right_label_value("Total", _format_money(ctx["totals"]["total"])))
    lines.append(_divider())
    lines.append(_line(f"Metodo de pago: {ctx['payment']['method_label_es']}"))
    lines.append(_line(f"Monto pagado: {_format_money(ctx['payment']['amount_paid'])}"))
    if ctx["payment"]["reference"]:
        lines.append(_line(f"Referencia: {ctx['payment']['reference']}"))
    if ctx["payment"]["change_due"] > 0:
        lines.append(_line(f"Cambio: {_format_money(ctx['payment']['change_due'])}"))
    lines.append(_divider())
    lines.append(_center("Gracias por su visita"))
    lines.append(_center("GastroPOSV by MEKA"))

    text = "\n".join(lines)
    items_html = "".join(
        f"<tr><td>{item['qty']}</td><td>{item['name']}</td><td>{_format_money(Decimal(str(item['unit_price'])))}</td><td>{_format_money(Decimal(str(item['line_total'])))}</td></tr>"
        for item in ctx["items"]
    )
    center_html = "".join(f"<div class='center'>{line}</div>" for line in center_lines)
    html = (
        "<div class='ticket'>"
        "<style>"
        ".ticket{font-family:Courier,monospace;font-size:10px;text-align:center}"
        ".center{line-height:1.2}"
        ".items{width:100%;font-size:11px;border-collapse:collapse}"
        ".items th,.items td{padding:1px 0;vertical-align:top}"
        ".items th{text-align:right}"
        ".items th:nth-child(2),.items td:nth-child(2){text-align:left;padding:0 4px}"
        ".items td{text-align:right}"
        "</style>"
        f"{center_html}"
        "<table class='items'><thead><tr><th>CANT</th><th>DESCRIPCION</th><th>P.UNIT</th><th>TOTAL</th></tr></thead><tbody>"
        f"{items_html}"
        "</tbody></table>"
        "</div>"
    )
    return {
        "text": text,
        "html": html,
        "meta": {
            "order_id": order.id,
            "type": "customer",
            "payment_status": order.payment_status,
            "cat017_code": ctx["payment"]["method_code_cat017"],
            "public_url": ctx["public_url"],
            "qr_value": ctx["qr_value"],
            "logo_path": ctx["logo_path"],
            "logo_exists": ctx["logo_exists"],
            "receipt_context": ctx,
            "pdf_center_lines": center_lines,
        },
    }


def render_closeout_ticket(session, summary: dict) -> dict:
    now = timezone.localtime(session.closed_at or timezone.now())
    lines: list[str] = []
    lines.append(_line("GastroPOSV"))
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
    lines.append(_line("GastroPOSV"))
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
    lines.append(_line("GastroPOSV"))
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
