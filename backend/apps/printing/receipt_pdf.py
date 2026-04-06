from __future__ import annotations

import re
from dataclasses import dataclass
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


def build_receipt_pdf(
    *,
    lines: list[str] | tuple[str, ...],
    filename: str,
    page_width_mm: float = 80.0,
    max_chars_per_line: int = 42,
    font_size: float = 9.0,
    line_height: float = 11.0,
) -> ReceiptPdfResult:
    clean_lines = _normalize_lines(lines, max_chars_per_line=max_chars_per_line)
    try:
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas

        font_name = _register_mono_font()
        page_width = page_width_mm * mm
        margin_x = 4 * mm
        margin_y = 4 * mm
        page_height = max((len(clean_lines) * line_height) + (margin_y * 2), 40 * mm)

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
        fallback = SimpleTextPdfWriter(page_width=612, page_height=792, font_name="Courier", font_size=10, line_height=14)
        for line in clean_lines:
            fallback.writeLine(line)
        pdf_bytes = fallback.build()
    return ReceiptPdfResult(pdf_bytes=pdf_bytes, filename=filename)


def build_receipt_pdf_from_text(*, text: str, filename: str, **kwargs) -> ReceiptPdfResult:
    lines = sanitize_receipt_text(text).split("\n")
    return build_receipt_pdf(lines=lines, filename=filename, **kwargs)
