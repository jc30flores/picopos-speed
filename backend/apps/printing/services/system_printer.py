from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


STAR_QUEUE = "star_tsp100"
DRAWER_RAW_COMMAND = r"""printf '\x1b\x07\x0b\x19\x07' | lp -d star_tsp100 -o raw"""

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

    def check_queue_exists(self, *, context: dict | None = None, endpoint: str | None = None) -> bool:
        result = self.run_command(["lpstat", "-p", self.queue], timeout=8, context=context, endpoint=endpoint)
        return result.ok and self.queue in (result.stdout + result.stderr)

    def print_ticket_text(self, ticket_text: str, *, context: dict | None = None, endpoint: str | None = None) -> tuple[bool, str | None]:
        if not self.check_queue_exists(context=context, endpoint=endpoint):
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
        result = self.run_command(
            ["/bin/bash", "-lc", DRAWER_RAW_COMMAND],
            timeout=10,
            context=context,
            endpoint=endpoint,
        )
        if result.ok:
            return True, None
        return False, (result.stderr or result.stdout or "Cash drawer command failed").strip()

    def generate_receipt_pdf(self, ticket_text: str, *, order_id: int, payment_id: int | None = None) -> tuple[str, str]:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        receipts_dir = Path(settings.MEDIA_ROOT) / "receipts"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        filename = f"receipt_{order_id}_{payment_id or 'na'}_{ts}.pdf"
        filepath = receipts_dir / filename

        pdf = canvas.Canvas(str(filepath), pagesize=A4)
        pdf.setFont("Courier", 10)
        y = 820
        for line in (ticket_text or "").splitlines():
            pdf.drawString(36, y, line)
            y -= 12
            if y < 36:
                pdf.showPage()
                pdf.setFont("Courier", 10)
                y = 820
        pdf.save()

        media_url = str(settings.MEDIA_URL).rstrip("/")
        url = f"{media_url}/receipts/{filename}"
        return str(filepath), url

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
