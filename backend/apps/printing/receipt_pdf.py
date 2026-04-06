from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from math import floor
from pathlib import Path
from textwrap import wrap
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from apps.printing.services.pdf_text import SimpleTextPdfWriter

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
        return build_sale_receipt_pdf(
            receipt_context=receipt_context,
            filename=filename,
            logo_path=kwargs.get("logo_path"),
            qr_value=kwargs.get("qr_value"),
            page_width_mm=kwargs.get("page_width_mm"),
        )
    lines = sanitize_receipt_text(text).split("\n")
    return build_receipt_pdf(lines=lines, filename=filename, **kwargs)


def _money(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _brand_name(ctx: dict) -> str:
    raw = str(ctx.get("tagline") or ctx.get("restaurant_name") or "Pico de Gallo").strip()
    if raw.lower().startswith("pico de gallo"):
        return "Pico de Gallo"
    return raw or "Pico de Gallo"


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
    margin_x = mm_to_points(3.0)
    margin_y = mm_to_points(3.0)
    content_width = max(1.0, page_width_pt - margin_x * 2)
    general_size = 8.2
    item_size = 9.1
    leading = 9.9
    item_leading = 11.0

    logo_reader = None
    logo_w = logo_h = 0.0
    candidate = Path(logo_path or "")
    if candidate.exists():
        try:
            logo_reader = ImageReader(str(candidate))
            img_w, img_h = logo_reader.getSize()
            if img_w and img_h:
                logo_w = min(content_width * 0.78, mm_to_points(60))
                logo_h = logo_w * float(img_h) / float(img_w)
        except Exception:
            logo_reader = None

    qr_reader = None
    qr_size = min(content_width * 0.60, mm_to_points(31))
    if qr_value:
        try:
            import qrcode

            qr_img = qrcode.make(sanitize_receipt_text(str(qr_value)))
            qr_reader = ImageReader(qr_img)
        except Exception:
            qr_reader = None

    totals = receipt_context.get("totals") or {}
    total = _money(totals.get("total") or 0)
    subtotal = _money(totals.get("subtotal") or (total / Decimal("1.13")))
    iva = _money(totals.get("iva") or (total - subtotal))
    if subtotal + iva != total:
        iva = _money(total - subtotal)

    dte = receipt_context.get("dte") or {}
    address_lines = wrap(str(receipt_context.get("address") or ""), width=max(18, int((content_width / max(pdfmetrics.stringWidth("0", font_name, general_size), 1))))) or []
    center_lines = [
        _brand_name(receipt_context),
        *address_lines,
        "DATOS DTE",
        f"No. Control: {dte.get('numero_control') or '-'}",
        f"Codigo Gen: {dte.get('codigo_generacion') or '-'}",
        f"Fecha DTE: {dte.get('fecha_dte') or '-'}",
    ]
    center_lines = [line for line in center_lines if str(line).strip()]

    items = receipt_context.get("items") or []
    cols = max(30, int(content_width / max(pdfmetrics.stringWidth("0", font_name, item_size), 1)))
    col_qty, col_unit, col_total = 4, 9, 9
    col_desc = max(10, cols - col_qty - col_unit - col_total - 3)
    item_lines = [f"{'CANT':<{col_qty}} {'DESCRIPCION':<{col_desc}} {'P.UNIT':>{col_unit}} {'TOTAL':>{col_total}}"]
    for row in items:
        qty = str(row.get("qty", ""))
        name = str(row.get("name", ""))
        unit = f"${_money(row.get('unit_price')):.2f}"
        line_total = f"${_money(row.get('line_total')):.2f}"
        parts = wrap(name, width=col_desc, break_long_words=True, break_on_hyphens=False) or [""]
        item_lines.append(f"{qty[:col_qty]:<{col_qty}} {parts[0]:<{col_desc}} {unit:>{col_unit}} {line_total:>{col_total}}")
        for extra in parts[1:]:
            item_lines.append(f"{'':<{col_qty}} {extra:<{col_desc}} {'':>{col_unit}} {'':>{col_total}}")

    details_lines = [
        receipt_context.get("service_type_label") or "",
        f"Atendido por: {receipt_context.get('cashier_name') or '-'}",
        f"Orden #{receipt_context.get('order_number') or '-'}",
        (receipt_context.get("order_datetime").strftime("%Y-%m-%d %H:%M") if receipt_context.get("order_datetime") else ""),
    ]
    details_lines = [line for line in details_lines if line]
    payment = receipt_context.get("payment") or {}
    payment_lines = [
        f"Metodo de pago: {payment.get('method_label_es') or '-'}",
        f"Monto pagado: ${_money(payment.get('amount_paid') or 0):.2f}",
    ]
    if payment.get("reference"):
        payment_lines.append(f"Referencia: {payment.get('reference')}")
    if _money(payment.get("change_due") or 0) > 0:
        payment_lines.append(f"Cambio: ${_money(payment.get('change_due')):.2f}")

    height_pt = max(
        mm_to_points(120),
        margin_y
        + logo_h
        + (len(center_lines) * leading)
        + (qr_size + leading if qr_reader else 0)
        + (len(details_lines) * leading)
        + (len(item_lines) * item_leading)
        + (8 * leading)
        + margin_y
        + mm_to_points(8),
    )
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=(page_width_pt, height_pt), pageCompression=0)
    y = height_pt - margin_y

    if logo_reader and logo_w > 0 and logo_h > 0:
        y -= logo_h
        pdf.drawImage(logo_reader, (page_width_pt - logo_w) / 2.0, y, width=logo_w, height=logo_h, preserveAspectRatio=True, mask="auto")
        y -= leading * 0.4

    pdf.setFont(font_name, general_size)
    for line in center_lines:
        y -= leading
        tw = pdfmetrics.stringWidth(line, font_name, general_size)
        pdf.drawString(max(margin_x, (page_width_pt - tw) / 2.0), y, line)

    if qr_reader:
        y -= leading * 0.4
        y -= qr_size
        pdf.drawImage(qr_reader, (page_width_pt - qr_size) / 2.0, y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask="auto")
        y -= leading * 0.5

    def hr() -> None:
        nonlocal y
        y -= leading * 0.55
        pdf.setLineWidth(0.7)
        pdf.line(margin_x, y, page_width_pt - margin_x, y)
        y -= leading * 0.35

    hr()
    for line in details_lines:
        y -= leading
        tw = pdfmetrics.stringWidth(line, font_name, general_size)
        pdf.drawString(max(margin_x, (page_width_pt - tw) / 2.0), y, line)
    hr()
    pdf.setFont(font_name, item_size)
    for line in item_lines:
        y -= item_leading
        pdf.drawString(margin_x, y, line)
    pdf.setFont(font_name, general_size)
    hr()
    for label, amount in [("Subtotal", subtotal), ("IVA", iva), ("Total", total)]:
        text = f"{label}:"
        value = f"${amount:.2f}"
        space = int(cols - len(text) - len(value) - 1)
        pdf.drawString(margin_x, y - leading, (f"{text}{' ' * max(1, space)} {value}")[: max(1, cols)])
        y -= leading
    hr()
    for line in payment_lines:
        y -= leading
        pdf.drawString(margin_x, y, line)
    hr()
    footer = "Gracias por su visita"
    y -= leading
    tw = pdfmetrics.stringWidth(footer, font_name, general_size)
    pdf.drawString(max(margin_x, (page_width_pt - tw) / 2.0), y, footer)
    pdf.save()
    return ReceiptPdfResult(pdf_bytes=stream.getvalue(), filename=filename)
