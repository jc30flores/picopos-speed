from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from io import BytesIO
from math import floor
from pathlib import Path
from textwrap import wrap
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from apps.printing.services.pdf_text import SimpleTextPdfWriter

logger = logging.getLogger(__name__)

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_ESC_POS_RE = re.compile(r"\x1b(?:[@-~]|\[[0-?]*[ -/]*[@-~])")
_QR_URL_RE = re.compile(r"https?://admin\.factura\.gob\.sv/\S*", re.IGNORECASE)
_CENTER_MARKER = "<<CENTER>>"
_ITEM_MARKER = "<<ITEM>>"
_FONT_NAME = "ReceiptMono"
_FONT_REGISTERED = False


@dataclass(frozen=True)
class ReceiptPdfResult:
    pdf_bytes: bytes
    filename: str


def mm_to_points(mm_value: float) -> float:
    return float(mm_value) * 72.0 / 25.4


def get_printer_size_mm() -> float:
    value = getattr(settings, "PRINTER_SIZE", getattr(settings, "PRINTER_SIZE_MM", 80.0))
    try:
        parsed = float(value)
        return parsed if parsed > 0 else 80.0
    except (TypeError, ValueError):
        return 80.0


def get_ticket_page_size(*, lines_count: int, line_height: float, margins_mm: float, width_mm: float) -> tuple[float, float]:
    width_pt = mm_to_points(width_mm)
    margin_pt = mm_to_points(margins_mm)
    height_pt = max((lines_count * line_height) + (margin_pt * 2), mm_to_points(20))
    return width_pt, height_pt


def _register_mono_font() -> str:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return _FONT_NAME

    candidates = [
        getattr(settings, "RECEIPT_MONO_FONT_PATH", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        str(Path(settings.BASE_DIR) / "venv/lib/python3.12/site-packages/barcode/fonts/DejaVuSansMono.ttf"),
    ]
    for candidate in candidates:
        path = Path(candidate or "")
        if not path.exists():
            continue
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont

            pdfmetrics.registerFont(TTFont(_FONT_NAME, str(path)))
            _FONT_REGISTERED = True
            return _FONT_NAME
        except Exception:
            continue
    return "Courier"


def sanitize_receipt_text(text: str) -> str:
    raw = str(text or "")
    without_escpos = _ESC_POS_RE.sub("", raw)
    without_controls = _CONTROL_CHARS_RE.sub("", without_escpos)
    return without_controls.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_lines(lines: list[str] | tuple[str, ...], *, max_chars_per_line: int) -> list[str]:
    out: list[str] = []
    for raw_line in lines:
        line = sanitize_receipt_text(raw_line).strip("\n")
        if line.strip() and set(line.strip()) <= {"-", "_"}:
            out.append(line.strip()[:max_chars_per_line])
            continue
        wrapped = wrap(
            line,
            width=max_chars_per_line,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        out.extend(chunk.rstrip() for chunk in wrapped)
    while len(out) > 1 and out[-1] == "":
        out.pop()
    return out or [""]


def _resolve_max_chars_per_line(
    *,
    page_width_pt: float,
    margins_mm: float,
    font_name: str,
    font_size: float,
    max_chars_per_line: int | None = None,
) -> int:
    content_width_pt = max(1.0, page_width_pt - (mm_to_points(margins_mm) * 2))
    computed_max = 42
    try:
        from reportlab.pdfbase import pdfmetrics

        char_width_pt = pdfmetrics.stringWidth("0", font_name, font_size)
        if char_width_pt > 0:
            computed_max = max(8, int(floor(content_width_pt / char_width_pt)))
    except Exception:
        approx_char_width = max(1.0, font_size * 0.6)
        computed_max = max(8, int(floor(content_width_pt / approx_char_width)))

    if max_chars_per_line is not None and max_chars_per_line > 0:
        return max(8, min(computed_max, int(max_chars_per_line)))
    return computed_max


def build_receipt_pdf(
    *,
    lines: list[str] | tuple[str, ...],
    filename: str,
    page_width_mm: float | None = None,
    max_chars_per_line: int | None = None,
    font_size: float = 8.2,
    line_height: float = 9.8,
    margins_mm: float = 3.0,
    logo_path: str | None = None,
    qr_value: str | None = None,
    qr_title: str | None = None,
    center_lines: list[str] | None = None,
    suppress_qr_url_lines: bool = False,
) -> ReceiptPdfResult:
    target_width_mm = page_width_mm if page_width_mm is not None else get_printer_size_mm()
    font_name = _register_mono_font()
    page_width_pt = mm_to_points(target_width_mm)
    resolved_max_chars = _resolve_max_chars_per_line(
        page_width_pt=page_width_pt,
        margins_mm=margins_mm,
        font_name=font_name,
        font_size=font_size,
        max_chars_per_line=max_chars_per_line,
    )
    clean_lines = _normalize_lines(lines, max_chars_per_line=resolved_max_chars)
    if suppress_qr_url_lines:
        clean_lines = [line for line in clean_lines if not _QR_URL_RE.search(line)]

    margin_x = mm_to_points(margins_mm)
    margin_y = mm_to_points(margins_mm)
    leading = max(line_height, font_size + 1.2)

    try:
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen import canvas

        content_width = max(1.0, page_width_pt - (margin_x * 2))
        centered = [sanitize_receipt_text(line).strip() for line in (center_lines or []) if str(line or "").strip()]

        logo_reader = None
        logo_draw_width = 0.0
        logo_draw_height = 0.0
        logo_padding_bottom = 0.0
        if logo_path:
            candidate = Path(logo_path)
            if candidate.exists():
                try:
                    logo_reader = ImageReader(str(candidate))
                    img_w, img_h = logo_reader.getSize()
                    if img_w and img_h:
                        logo_draw_width = min(content_width * 0.75, mm_to_points(55))
                        logo_draw_height = logo_draw_width * (float(img_h) / float(img_w))
                        logo_padding_bottom = leading * 0.5
                except Exception:
                    logo_reader = None

        qr_size = 0.0
        qr_padding_top = 0.0
        qr_reader = None
        if qr_value:
            qr_size = min(content_width * 0.58, mm_to_points(32))
            qr_padding_top = leading * 0.5
            try:
                import qrcode

                qr_img = qrcode.make(sanitize_receipt_text(str(qr_value)))
                qr_reader = ImageReader(qr_img)
            except Exception:
                qr_reader = None

        item_font_size = font_size + 0.8
        item_leading = leading + 0.9
        line_segments: list[tuple[str, bool, bool, bool]] = []
        for line in clean_lines:
            is_center = line.startswith(_CENTER_MARKER)
            is_item = line.startswith(_ITEM_MARKER)
            line_text = line
            if is_center:
                line_text = line_text[len(_CENTER_MARKER):]
            if is_item:
                line_text = line_text[len(_ITEM_MARKER):]
            normalized = line_text.strip()
            is_rule = bool(normalized and set(normalized) <= {"-", "_"} and len(normalized) >= 3)
            line_segments.append((line_text, is_rule, is_center, is_item))
        text_height = sum((leading * 0.9) if is_rule else (item_leading if is_item else leading) for _, is_rule, _, is_item in line_segments)

        page_height = max(
            mm_to_points(35),
            margin_y
            + logo_draw_height
            + logo_padding_bottom
            + (len(centered) * leading)
            + qr_padding_top
            + qr_size
            + (leading * 0.4 if qr_size > 0 else 0.0)
            + text_height
            + margin_y,
        )

        stream = BytesIO()
        pdf = canvas.Canvas(stream, pagesize=(page_width_pt, page_height), pageCompression=0)
        pdf.setFont(font_name, font_size)

        y = page_height - margin_y

        if logo_reader and logo_draw_width > 0 and logo_draw_height > 0:
            x_logo = (page_width_pt - logo_draw_width) / 2.0
            y -= logo_draw_height
            pdf.drawImage(logo_reader, x_logo, y, width=logo_draw_width, height=logo_draw_height, preserveAspectRatio=True, mask="auto")
            y -= logo_padding_bottom

        for line in centered:
            y -= leading
            text_width = pdfmetrics.stringWidth(line, font_name, font_size)
            x_line = max(margin_x, (page_width_pt - text_width) / 2.0)
            pdf.drawString(x_line, y, line)

        if qr_reader and qr_size > 0:
            y -= qr_padding_top
            y -= qr_size
            pdf.drawImage(qr_reader, (page_width_pt - qr_size) / 2.0, y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")
            y -= leading * 0.4

        for line, is_rule, is_center, is_item in line_segments:
            if is_rule:
                y -= leading * 0.55
                pdf.setLineWidth(0.7)
                pdf.line(margin_x, y, page_width_pt - margin_x, y)
                y -= leading * 0.35
                continue
            active_size = item_font_size if is_item else font_size
            active_leading = item_leading if is_item else leading
            pdf.setFont(font_name, active_size)
            y -= active_leading
            if is_center:
                text_width = pdfmetrics.stringWidth(line, font_name, active_size)
                x_line = max(margin_x, (page_width_pt - text_width) / 2.0)
                pdf.drawString(x_line, y, line)
            else:
                pdf.drawString(margin_x, y, line)
            pdf.setFont(font_name, font_size)

        pdf.save()
        pdf_bytes = stream.getvalue()
    except Exception:
        page_width, page_height = get_ticket_page_size(
            lines_count=len(clean_lines),
            line_height=line_height,
            margins_mm=margins_mm,
            width_mm=target_width_mm,
        )
        fallback = SimpleTextPdfWriter(
            page_width=int(round(page_width)),
            page_height=int(round(page_height)),
            font_name="Courier",
            font_size=int(round(font_size)),
            line_height=int(round(line_height)),
            left_margin=int(round(margin_x)),
            right_margin=int(round(margin_x)),
            top_margin=int(round(margin_y)),
            bottom_margin=int(round(margin_y)),
        )
        for line in clean_lines:
            fallback.writeLine(line)
        pdf_bytes = fallback.build()

    return ReceiptPdfResult(pdf_bytes=pdf_bytes, filename=filename)


def build_receipt_pdf_from_text(*, text: str, filename: str, **kwargs) -> ReceiptPdfResult:
    receipt_context = kwargs.pop("receipt_context", None)
    if receipt_context:
        try:
            return build_sale_receipt_pdf(
                receipt_context=receipt_context,
                filename=filename,
                logo_path=kwargs.get("logo_path") or _ticket_logo_path_from_settings(),
                qr_value=kwargs.get("qr_value"),
                page_width_mm=kwargs.get("page_width_mm"),
            )
        except ModuleNotFoundError as exc:
            logger.exception(
                "[TICKET_TRACE] generator=V2_LOGO_QR_RENDERER active=False dependency_missing=%s filename=%s",
                exc,
                filename,
            )
            raise
    lines = sanitize_receipt_text(text).split("\n")
    return build_receipt_pdf(lines=lines, filename=filename, **kwargs)


def _money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _brand_name(ctx: dict) -> str:
    raw = str(ctx.get("tagline") or ctx.get("restaurant_name") or "GastroPOSV").strip()
    if raw.lower().startswith("pico de gallo"):
        return "GastroPOSV"
    return raw or "GastroPOSV"


def clean_display(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "undefined"}:
        return fallback
    return text


def _default_qr_value(receipt_context: dict) -> str:
    dte = receipt_context.get("dte") or {}
    totals = receipt_context.get("totals") or {}
    codigo = clean_display(dte.get("codigo_generacion"))
    numero = clean_display(dte.get("numero_control"))
    fecha = clean_display(dte.get("fecha_dte")) or clean_display(receipt_context.get("order_datetime"))
    total = clean_display(totals.get("total"))
    if codigo or numero:
        return " | ".join(part for part in [f"CG:{codigo}" if codigo else "", f"NC:{numero}" if numero else "", f"FECHA:{fecha}" if fecha else "", f"TOTAL:{total}" if total else ""] if part)
    return " | ".join(part for part in [f"ORDEN:{clean_display(receipt_context.get('order_number'), '-')}", f"FECHA:{fecha}" if fecha else "", f"TOTAL:{total}" if total else ""] if part)


def _ticket_logo_path_from_settings() -> str | None:
    try:
        from apps.core.ticket_settings import get_ticket_logo_path

        return get_ticket_logo_path()
    except Exception as exc:
        logger.warning("receipt_pdf.ticket_logo_settings_unavailable error=%s", exc)
        return None


def _wrap_line(text: str, width: int) -> list[str]:
    return wrap(str(text), width=max(8, width), break_long_words=True, break_on_hyphens=False) or [str(text)]


def _dte_status_label(receipt_context: dict) -> str:
    dte = receipt_context.get("dte") or {}
    raw = clean_display(dte.get("estado_dte") or dte.get("estado_hacienda") or dte.get("status"), "")
    if raw:
        text = raw.upper()
        if text in {"ACEPTADO", "PROCESADO", "RECIBIDO", "OK"}:
            return "ACEPTADO"
        if text in {"RECHAZADO", "FAILED", "ERROR", "INVALIDO", "INVÁLIDO"}:
            return "RECHAZADO"
        if text in {"INVALIDADO", "ANULADO"}:
            return "INVALIDADO"
        return "PENDIENTE"
    if clean_display(dte.get("numero_control")) or clean_display(dte.get("codigo_generacion")):
        return "PENDIENTE"
    return "SIN DTE"


def _receipt_qr_value(receipt_context: dict, explicit_value: str | None = None) -> str:
    dte = receipt_context.get("dte") or {}
    totals = receipt_context.get("totals") or {}
    status = _dte_status_label(receipt_context)
    codigo = clean_display(dte.get("codigo_generacion"))
    numero = clean_display(dte.get("numero_control"))
    fecha = clean_display(dte.get("fecha_dte")) or clean_display(receipt_context.get("order_datetime"))
    total = clean_display(totals.get("total"))
    sello = clean_display(dte.get("sello_recibido"))
    if codigo or numero:
        return " | ".join(
            part
            for part in [
                f"CG:{codigo}" if codigo else "",
                f"NC:{numero}" if numero else "",
                f"FECHA:{fecha}" if fecha else "",
                f"TOTAL:{total}" if total else "",
                f"ESTADO:{status}",
                f"SELLO:{sello}" if sello else "",
            ]
            if part
        )
    return " | ".join(part for part in [f"ORDEN:{clean_display(receipt_context.get('order_number'), '-')}", f"FECHA:{fecha}" if fecha else "", f"TOTAL:{total}" if total else "", "ESTADO:SIN DTE"] if part)


def _draw_centered_text(pdf, text: str, *, y: float, page_width_pt: float, margin_x: float, font_name: str, font_size: float) -> None:
    from reportlab.pdfbase import pdfmetrics

    width = pdfmetrics.stringWidth(text, font_name, font_size)
    pdf.drawString(max(margin_x, (page_width_pt - width) / 2.0), y, text)


def _draw_right_value(pdf, label: str, value: str, *, y: float, page_width_pt: float, margin_x: float, font_name: str, font_size: float) -> None:
    from reportlab.pdfbase import pdfmetrics

    pdf.setFont(font_name, font_size)
    pdf.drawString(margin_x, y, label)
    value_width = pdfmetrics.stringWidth(value, font_name, font_size)
    pdf.drawString(max(margin_x, page_width_pt - margin_x - value_width), y, value)


def build_sale_receipt_pdf(
    *,
    receipt_context: dict,
    filename: str,
    logo_path: str | None = None,
    qr_value: str | None = None,
    page_width_mm: float | None = None,
) -> ReceiptPdfResult:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfgen import canvas

    font_name = _register_mono_font()
    width_mm = page_width_mm if page_width_mm is not None else get_printer_size_mm()
    page_width_pt = mm_to_points(width_mm)
    margin_x = mm_to_points(2.5)
    margin_y = mm_to_points(2.4)
    content_width = max(1.0, page_width_pt - margin_x * 2)
    body_size = 6.6
    small_size = 6.2
    header_size = 9.2
    section_size = 7.2
    total_size = 8.0
    leading = 7.7
    small_leading = 7.0
    item_leading = 7.4

    logo_reader = None
    logo_w = logo_h = 0.0
    resolved_logo_path = logo_path or _ticket_logo_path_from_settings()
    if resolved_logo_path:
        candidate = Path(resolved_logo_path)
        if candidate.exists():
            try:
                logo_reader = ImageReader(str(candidate))
                img_w, img_h = logo_reader.getSize()
                if img_w and img_h:
                    logo_w = min(content_width * 0.62, mm_to_points(46))
                    logo_h = logo_w * float(img_h) / float(img_w)
                    max_logo_h = mm_to_points(22)
                    if logo_h > max_logo_h:
                        logo_h = max_logo_h
                        logo_w = logo_h * float(img_w) / float(img_h)
            except Exception as exc:
                logger.warning("receipt_pdf.ticket_logo_load_failed path=%s error=%s", resolved_logo_path, exc)
                logo_reader = None

    qr_reader = None
    qr_drawing = None
    qr_size = min(content_width * 0.50, mm_to_points(28))
    qr_payload = _receipt_qr_value(receipt_context, qr_value)
    if qr_payload:
        try:
            import qrcode

            qr_img = qrcode.make(sanitize_receipt_text(str(qr_payload)))
            qr_reader = ImageReader(qr_img)
        except Exception:
            try:
                from reportlab.graphics.barcode.qr import QrCodeWidget
                from reportlab.graphics.shapes import Drawing

                qr_widget = QrCodeWidget(sanitize_receipt_text(str(qr_payload)))
                bounds = qr_widget.getBounds()
                qr_width = bounds[2] - bounds[0]
                qr_height = bounds[3] - bounds[1]
                qr_drawing = Drawing(qr_size, qr_size, transform=[qr_size / qr_width, 0, 0, qr_size / qr_height, 0, 0])
                qr_drawing.add(qr_widget)
            except Exception as exc:
                logger.warning("receipt_pdf.qr_build_failed error=%s", exc)
                qr_reader = None
                qr_drawing = None

    totals = receipt_context.get("totals") or {}
    total = _money(totals.get("total") or 0)
    subtotal = _money(totals.get("subtotal") or (total / Decimal("1.13")))
    iva = _money(totals.get("iva") or (total - subtotal))
    if subtotal + iva != total:
        iva = _money(total - subtotal)

    dte = receipt_context.get("dte") or {}
    status_label = _dte_status_label(receipt_context)
    center_cols = max(30, int(content_width / max(pdfmetrics.stringWidth("0", font_name, body_size), 1)))
    brand_lines = _wrap_line(_brand_name(receipt_context).upper(), center_cols)
    address_lines = _wrap_line(str(receipt_context.get("address") or ""), center_cols) if receipt_context.get("address") else []
    contact_lines = []
    if receipt_context.get("phone"):
        contact_lines.extend(_wrap_line(f"Tel: {receipt_context.get('phone')}", center_cols))

    dte_lines: list[str] = [
        f"No. Control: {clean_display(dte.get('numero_control'), '-')}",
        f"Codigo Gen: {clean_display(dte.get('codigo_generacion'), '-')}",
        f"Sello Recibido: {clean_display(dte.get('sello_recibido'), '-') if status_label == 'ACEPTADO' else clean_display(dte.get('sello_recibido'), 'Pendiente' if status_label == 'PENDIENTE' else '-')}",
    ]
    dte_font_size = 5.2
    longest_dte = max((pdfmetrics.stringWidth(line, font_name, dte_font_size) for line in dte_lines), default=0)
    if longest_dte > content_width:
        dte_font_size = max(4.4, dte_font_size * content_width / longest_dte)
    dte_leading = max(5.2, dte_font_size + 1.0)

    order_dt = receipt_context.get("order_datetime")
    details_lines = [
        receipt_context.get("service_type_label") or "RESTAURANTE",
        f"Orden: #{receipt_context.get('order_number') or '-'}",
        f"Fecha: {order_dt.strftime('%Y-%m-%d %H:%M') if order_dt else '-'}",
    ]

    items = receipt_context.get("items") or []
    cols = max(36, int(content_width / max(pdfmetrics.stringWidth("0", font_name, small_size), 1)))
    col_qty, col_total = 4, 10
    col_desc = max(16, cols - col_qty - col_total - 2)
    item_lines: list[tuple[str, bool]] = [(f"{'CANT':<{col_qty}} {'DESCRIPCION':<{col_desc}} {'TOTAL':>{col_total}}", True)]
    for row in items:
        qty = str(row.get("qty", ""))
        name = str(row.get("name", ""))
        is_modifier = name.strip().startswith("+") or name.strip().startswith("-")
        unit = f"${_money(row.get('unit_price')):.2f}"
        line_total = f"${_money(row.get('line_total')):.2f}"
        desc_width = col_desc - (2 if is_modifier else 0)
        parts = wrap(name, width=max(8, desc_width), break_long_words=True, break_on_hyphens=False) or [""]
        prefix_qty = "" if is_modifier else qty[:col_qty]
        desc_prefix = "  " if is_modifier else ""
        item_lines.append((f"{prefix_qty:<{col_qty}} {desc_prefix}{parts[0]:<{desc_width}} {line_total:>{col_total}}", False))
        for extra in parts[1:]:
            item_lines.append((f"{'':<{col_qty}} {desc_prefix}{extra:<{desc_width}} {'':>{col_total}}", False))
        if not is_modifier:
            item_lines.append((f"{'':<{col_qty}} {'P.Unit ' + unit:<{col_desc}} {'':>{col_total}}", False))

    payment = receipt_context.get("payment") or {}
    payment_lines = [
        ("Metodo:", payment.get("method_label_es") or "-"),
        ("Pagado:", f"${_money(payment.get('amount_paid') or 0):.2f}"),
    ]
    if payment.get("reference"):
        payment_lines.append(("Referencia:", str(payment.get("reference"))))
    if _money(payment.get("change_due") or 0) > 0:
        payment_lines.append(("Cambio:", f"${_money(payment.get('change_due')):.2f}"))

    optional_info: list[str] = []
    if clean_display(dte.get("telefono_cliente_display")):
        optional_info.append(f"Cliente: {clean_display(dte.get('telefono_cliente_display'))}")
    if clean_display(dte.get("descripcion_msg")):
        optional_info.append(f"Mensaje MH: {clean_display(dte.get('descripcion_msg'))}")
    optional_info = [part for line in optional_info for part in _wrap_line(line, center_cols)]

    # Exact one-page height budget: every drawing operation is counted once here.
    hr_height = leading * 0.75
    height_pt = (
        margin_y
        + (logo_h + leading * 0.30 if logo_reader and logo_w and logo_h else 0)
        + (len(brand_lines) * header_size)
        + (len(address_lines) * small_leading)
        + (len(contact_lines) * small_leading)
        + leading * 0.45
        + (len(dte_lines) * dte_leading)
        + hr_height
        + (len(details_lines) * leading)
        + hr_height
        + (len(item_lines) * item_leading)
        + hr_height
        + (4 * leading)
        + hr_height
        + (len(payment_lines) * leading)
        + (len(optional_info) * small_leading)
        + (qr_size + leading * 0.7 if (qr_reader or qr_drawing) else 0)
        + hr_height
        + leading
        + small_leading
        + margin_y
        + mm_to_points(3)
    )
    height_pt = max(mm_to_points(58), height_pt)

    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(page_width_pt, height_pt), pageCompression=0)
    y = height_pt - margin_y

    def move(amount: float) -> float:
        nonlocal y
        y -= amount
        return y

    def hr() -> None:
        move(leading * 0.38)
        pdf.setLineWidth(0.45)
        pdf.line(margin_x, y, page_width_pt - margin_x, y)
        move(leading * 0.37)

    if logo_reader and logo_w > 0 and logo_h > 0:
        move(logo_h)
        pdf.drawImage(logo_reader, (page_width_pt - logo_w) / 2.0, y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto")
        move(leading * 0.30)

    for line in brand_lines:
        pdf.setFont(font_name, header_size)
        move(header_size)
        _draw_centered_text(pdf, line, y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=header_size)
    pdf.setFont(font_name, small_size)
    for line in address_lines + contact_lines:
        move(small_leading)
        _draw_centered_text(pdf, line, y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=small_size)

    move(leading * 0.45)
    pdf.setFont(font_name, dte_font_size)
    for line in dte_lines:
        move(dte_leading)
        pdf.drawString(margin_x, y, line)

    hr()
    pdf.setFont(font_name, section_size)
    for index, line in enumerate(details_lines):
        size = section_size if index == 0 else body_size
        pdf.setFont(font_name, size)
        move(leading)
        _draw_centered_text(pdf, line, y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=size)

    hr()
    for line, is_header in item_lines:
        pdf.setFont(font_name, section_size if is_header else small_size)
        move(item_leading)
        pdf.drawString(margin_x, y, line)

    hr()
    for label, amount in [("Subtotal:", subtotal), ("IVA:", iva), ("TOTAL:", total)]:
        size = total_size if label == "TOTAL:" else body_size
        move(leading)
        _draw_right_value(pdf, label, f"${amount:.2f}", y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=size)

    hr()
    for label, value in payment_lines:
        move(leading)
        _draw_right_value(pdf, label, str(value), y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=body_size)
    pdf.setFont(font_name, small_size)
    for line in optional_info:
        move(small_leading)
        pdf.drawString(margin_x, y, line)

    if qr_reader or qr_drawing:
        move(leading * 0.45)
        move(qr_size)
        if qr_reader:
            pdf.drawImage(qr_reader, (page_width_pt - qr_size) / 2.0, y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")
        elif qr_drawing:
            from reportlab.graphics import renderPDF

            renderPDF.draw(qr_drawing, pdf, (page_width_pt - qr_size) / 2.0, y)
        move(leading * 0.25)

    hr()
    footer = "Gracias por su visita"
    brand_footer = "GastroPOSV by MEKA"
    pdf.setFont(font_name, small_size)
    pdf.setFillColorRGB(0, 0, 0)
    move(leading)
    _draw_centered_text(pdf, footer, y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=small_size)
    pdf.setFont(font_name, 5.6)
    pdf.setFillColorRGB(0.45, 0.45, 0.45)
    move(small_leading)
    _draw_centered_text(pdf, brand_footer, y=y, page_width_pt=page_width_pt, margin_x=margin_x, font_name=font_name, font_size=5.6)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.save()
    pdf_bytes = stream.getvalue()
    logger.info(
        "[TICKET_TRACE] generator=V2_LOGO_QR_RENDERER active=True logo_found=%s logo_path=%s qr_enabled=%s qr_payload_len=%s page_width_mm=%.2f page_height_pt=%.2f pdf_bytes=%s",
        bool(logo_reader),
        str(resolved_logo_path or ""),
        bool(qr_reader or qr_drawing),
        len(str(qr_payload or "")),
        float(width_mm),
        float(height_pt),
        len(pdf_bytes),
    )
    return ReceiptPdfResult(pdf_bytes=pdf_bytes, filename=filename)
