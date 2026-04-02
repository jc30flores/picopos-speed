from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


STAR_QUEUE = "star_tsp100"
DRAWER_RAW_COMMAND = r"""printf '\x1b\x07\x0b\x19\x07' | lp -d star_tsp100 -o raw"""
DRAWER_RAW_BYTES = bytes((0x1B, 0x07, 0x0B, 0x19, 0x07))
RECEIPT_PAGE_WIDTH_MM = 80
RECEIPT_LEFT_MARGIN_MM = 4
RECEIPT_TOP_BOTTOM_MARGIN_MM = 4
RECEIPT_LINE_HEIGHT_MM = 4.2
RECEIPT_MIN_HEIGHT_MM = 40

@dataclass
class CommandResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    elapsed_ms: int
    command: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SystemPrinterService:
    def __init__(self, queue: str = STAR_QUEUE):
        self.queue = queue

    def run_command(
        self,
        cmd: list[str] | str,
        *,
        input_bytes: bytes | None = None,
        timeout: int = 15,
        shell: bool = False,
        context: dict | None = None,
        endpoint: str | None = None,
    ) -> CommandResult:
        started = time.perf_counter()
        proc = subprocess.run(
            cmd,
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            shell=shell,
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        command_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        result = CommandResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=(proc.stdout or b"").decode(errors="replace"),
            stderr=(proc.stderr or b"").decode(errors="replace"),
            elapsed_ms=elapsed_ms,
            command=command_str,
        )
        logger.info(
            "printer.command timestamp=%s queue=%s endpoint=%s command=%s exit_code=%s elapsed_ms=%s stdout=%r stderr=%r context=%s",
            _now_iso(),
            self.queue,
            endpoint or "",
            command_str,
            result.exit_code,
            result.elapsed_ms,
            result.stdout,
            result.stderr,
            context or {},
        )
        return result

    def is_printer_available(self, *, context: dict | None = None, endpoint: str | None = None) -> bool:
        result = self.run_command(["lpstat", "-v"], timeout=8, context=context, endpoint=endpoint)
        if not result.ok:
            return False
        return self.queue in (result.stdout + result.stderr)

    def check_queue_exists(self, *, context: dict | None = None, endpoint: str | None = None) -> bool:
        # Backward-compatible alias for existing callers/tests.
        return self.is_printer_available(context=context, endpoint=endpoint)

    def print_ticket_text(self, ticket_text: str, *, context: dict | None = None, endpoint: str | None = None) -> tuple[bool, str | None]:
        logger.info("printer.ticket.attempt timestamp=%s queue=%s endpoint=%s context=%s", _now_iso(), self.queue, endpoint or "", context or {})
        if not self.is_printer_available(context=context, endpoint=endpoint):
            return False, f"Queue '{self.queue}' not found"
        with tempfile.NamedTemporaryFile(prefix="ticket_", suffix=".txt", delete=True) as temp:
            temp.write(ticket_text.encode("utf-8", errors="replace"))
            temp.flush()
            result = self.run_command(["lp", "-d", self.queue, temp.name], timeout=20, context=context, endpoint=endpoint)
        if result.ok:
            return True, None
        combined_error = (result.stderr or result.stdout or f"lp exited with code {result.exit_code}").strip()
        return False, combined_error

    def open_cash_drawer(self, *, context: dict | None = None, endpoint: str | None = None) -> tuple[bool, str | None]:
        logger.info(
            "printer.drawer.attempt timestamp=%s queue=%s endpoint=%s raw_equivalent=%s context=%s",
            _now_iso(),
            self.queue,
            endpoint or "",
            DRAWER_RAW_COMMAND,
            context or {},
        )
        if not self.is_printer_available(context=context, endpoint=endpoint):
            return False, f"Queue '{self.queue}' not found"
        result = self.run_command(
            ["lp", "-d", self.queue, "-o", "raw"],
            input_bytes=DRAWER_RAW_BYTES,
            timeout=10,
            context=context,
            endpoint=endpoint,
        )
        if result.ok:
            return True, None
        return False, (result.stderr or result.stdout or "Cash drawer command failed").strip()

    def generate_receipt_pdf(self, ticket_text: str, *, order_id: int, payment_id: int | None = None) -> tuple[str, str]:
        receipts_dir = Path(settings.MEDIA_ROOT) / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        filename = f"receipt_{order_id}_{payment_id or 'na'}_{ts}.pdf"
        filepath = receipts_dir / filename

        lines = (ticket_text or "").splitlines() or [""]
        try:
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas

            page_width = RECEIPT_PAGE_WIDTH_MM * mm
            left_margin = RECEIPT_LEFT_MARGIN_MM * mm
            top_bottom_margin = RECEIPT_TOP_BOTTOM_MARGIN_MM * mm
            line_height = RECEIPT_LINE_HEIGHT_MM * mm
            min_height = RECEIPT_MIN_HEIGHT_MM * mm
            page_height = max((len(lines) * line_height) + (top_bottom_margin * 2), min_height)

            buf = BytesIO()
            pdf = canvas.Canvas(buf, pagesize=(page_width, page_height))
            pdf.setFont("Courier", 8.5)
            text_obj = pdf.beginText(left_margin, page_height - top_bottom_margin)
            for line in lines:
                text_obj.textLine(line)
            pdf.drawText(text_obj)
            pdf.save()
            filepath.write_bytes(buf.getvalue())
        except Exception:
            filepath.write_bytes(self._fallback_pdf_bytes(lines))

        media_url = str(settings.MEDIA_URL).rstrip("/")
        url = f"{media_url}/receipts/{filename}"
        return str(filepath), url

    def _fallback_pdf_bytes(self, lines: list[str]) -> bytes:
        escaped_lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
        joined = "\\n".join(escaped_lines)
        content_lines = joined.replace("\\n", ") Tj T* (")
        content = f"BT /F1 10 Tf 24 760 Td ({content_lines}) Tj ET"
        objects = [
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
            f"4 0 obj << /Length {len(content)} >> stream\n{content}\nendstream endobj",
            "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Courier >> endobj",
        ]
        pdf = "%PDF-1.4\n"
        offsets: list[int] = []
        for obj in objects:
            offsets.append(len(pdf.encode("latin-1")))
            pdf += obj + "\n"
        xref_offset = len(pdf.encode("latin-1"))
        pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
        for off in offsets:
            pdf += f"{off:010d} 00000 n \n"
        pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
        return pdf.encode("latin-1", errors="ignore")

    def print_with_pdf_fallback(
        self,
        ticket_text: str,
        *,
        order_id: int,
        payment_id: int | None = None,
        context: dict | None = None,
        endpoint: str | None = None,
    ) -> dict:
        printed, print_error = self.print_ticket_text(ticket_text, context=context, endpoint=endpoint)
        receipt_pdf_url = None
        receipt_pdf_path = None
        if not printed:
            receipt_pdf_path, receipt_pdf_url = self.generate_receipt_pdf(
                ticket_text,
                order_id=order_id,
                payment_id=payment_id,
            )
            logger.warning(
                "printer.print_failed_fallback_pdf timestamp=%s queue=%s order_id=%s payment_id=%s error=%s pdf_path=%s pdf_url=%s",
                _now_iso(),
                self.queue,
                order_id,
                payment_id,
                print_error,
                receipt_pdf_path,
                receipt_pdf_url,
            )
        return {
            "printed": printed,
            "print_error": print_error,
            "receipt_pdf_url": receipt_pdf_url,
            "receipt_pdf_path": receipt_pdf_path,
        }
