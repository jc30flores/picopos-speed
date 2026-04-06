from __future__ import annotations

import re
from dataclasses import dataclass
from math import floor
from io import BytesIO
from pathlib import Path
from textwrap import wrap

from django.conf import settings
from apps.printing.services.pdf_text import SimpleTextPdfWriter

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_ESC_POS_RE = re.compile(r"\x1b(?:[@-~]|\[[0-?]*[ -/]*[@-~])")
_FONT_NAME = "ReceiptMono"
_FONT_REGISTERED = False


@dataclass(frozen=True)
class ReceiptPdfResult:
    pdf_bytes: bytes
    filename: str


def mm_to_points(mm_value: float) -> float:
    return float(mm_value) * 72.0 / 25.4


def get_printer_size_mm() -> float:
    value = getattr(settings, "PRINTER_SIZE", 80.0)
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
    page_width, page_height = get_ticket_page_size(
        lines_count=len(clean_lines),
        line_height=line_height,
        margins_mm=margins_mm,
        width_mm=target_width_mm,
    )
    margin_x = mm_to_points(margins_mm)
    margin_y = mm_to_points(margins_mm)
    try:
        from reportlab.pdfgen import canvas

        stream = BytesIO()
        pdf = canvas.Canvas(stream, pagesize=(page_width, page_height), pageCompression=0)
        text_obj = pdf.beginText(margin_x, page_height - margin_y - font_size)
        text_obj.setFont(font_name, font_size)
        text_obj.setLeading(line_height)
        for line in clean_lines:
            text_obj.textLine(line)
        pdf.drawText(text_obj)
        pdf.showPage()
        pdf.save()
        pdf_bytes = stream.getvalue()
    except Exception:
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
