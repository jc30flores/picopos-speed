from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from math import floor
from pathlib import Path
from textwrap import wrap

from django.conf import settings

from apps.printing.services.pdf_text import SimpleTextPdfWriter

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_ESC_POS_RE = re.compile(r"\x1b(?:[@-~]|\[[0-?]*[ -/]*[@-~])")
_QR_URL_RE = re.compile(r"https?://admin\.factura\.gob\.sv/\S*", re.IGNORECASE)
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
    font_size: float = 9.0,
    line_height: float = 11.0,
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

    try:
        from reportlab.graphics import renderPDF
        from reportlab.graphics.barcode import qr as rl_qr
        from reportlab.graphics.shapes import Drawing
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
                        logo_padding_bottom = line_height * 0.4
                except Exception:
                    logo_reader = None

        qr_size = 0.0
        qr_padding_top = 0.0
        qr_title_height = 0.0
        if qr_value:
            qr_size = min(content_width * 0.7, mm_to_points(42))
            qr_padding_top = line_height * 0.5
            qr_title_height = line_height if qr_title else 0.0

        page_height = max(
            mm_to_points(35),
            margin_y
            + logo_draw_height
            + logo_padding_bottom
            + (len(centered) * line_height)
            + qr_padding_top
            + qr_title_height
            + qr_size
            + (len(clean_lines) * line_height)
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
            y -= line_height
            text_width = pdfmetrics.stringWidth(line, font_name, font_size)
            x_line = max(margin_x, (page_width_pt - text_width) / 2.0)
            pdf.drawString(x_line, y, line)

        if qr_value and qr_size > 0:
            y -= qr_padding_top
            if qr_title:
                title = sanitize_receipt_text(qr_title).strip()
                y -= line_height
                text_width = pdfmetrics.stringWidth(title, font_name, font_size)
                pdf.drawString(max(margin_x, (page_width_pt - text_width) / 2.0), y, title)
            y -= qr_size
            qr_widget = rl_qr.QrCodeWidget(qr_value)
            bounds = qr_widget.getBounds()
            qr_w = bounds[2] - bounds[0]
            qr_h = bounds[3] - bounds[1]
            drawing = Drawing(qr_size, qr_size, transform=[qr_size / qr_w, 0, 0, qr_size / qr_h, 0, 0])
            drawing.add(qr_widget)
            renderPDF.draw(drawing, pdf, (page_width_pt - qr_size) / 2.0, y)
            y -= line_height * 0.5

        for line in clean_lines:
            normalized = line.strip()
            if normalized and set(normalized) <= {"-", "_"} and len(normalized) >= 3:
                y -= line_height * 0.6
                pdf.setLineWidth(0.7)
                pdf.line(margin_x, y, page_width_pt - margin_x, y)
                y -= line_height * 0.4
                continue
            y -= line_height
            pdf.drawString(margin_x, y, line)

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
    lines = sanitize_receipt_text(text).split("\n")
    return build_receipt_pdf(lines=lines, filename=filename, **kwargs)
