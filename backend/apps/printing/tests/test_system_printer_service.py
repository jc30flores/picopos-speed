from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.printing.services.system_printer import CommandResult, SystemPrinterService


class SystemPrinterServiceTests(SimpleTestCase):
    def test_is_printer_available_checks_lpstat_v(self):
        service = SystemPrinterService()
        with patch.object(
            service,
            "run_command",
            return_value=CommandResult(ok=True, exit_code=0, stdout="device for star_tsp100: usb://Star", stderr="", elapsed_ms=5, command="lpstat -v"),
        ):
            self.assertTrue(service.is_printer_available())

    def test_open_cash_drawer_uses_lp_raw_with_bytes(self):
        service = SystemPrinterService()
        with patch.object(service, "is_printer_available", return_value=True), patch.object(service, "run_command") as run_command:
            run_command.return_value = CommandResult(ok=True, exit_code=0, stdout="ok", stderr="", elapsed_ms=5, command="lp -d star_tsp100 -o raw")
            opened, error = service.open_cash_drawer()
        self.assertTrue(opened)
        self.assertIsNone(error)
        args, kwargs = run_command.call_args
        self.assertEqual(args[0], ["lp", "-d", "star_tsp100", "-o", "raw"])
        self.assertEqual(kwargs.get("input_bytes"), bytes((0x1B, 0x07, 0x0B, 0x19, 0x07)))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir(), MEDIA_URL="/media/")
    def test_print_with_pdf_fallback_printer_ok(self):
        service = SystemPrinterService()
        with patch.object(service, "check_queue_exists", return_value=True), patch.object(
            service,
            "run_command",
            return_value=CommandResult(ok=True, exit_code=0, stdout="ok", stderr="", elapsed_ms=5, command="lp -d star_tsp100 /tmp/x"),
        ):
            result = service.print_with_pdf_fallback("hello", order_id=10, payment_id=20)
        self.assertTrue(result["printed"])
        self.assertIsNone(result["receipt_pdf_url"])

    @override_settings(MEDIA_ROOT=tempfile.gettempdir(), MEDIA_URL="/media/")
    def test_print_with_pdf_fallback_queue_missing_generates_pdf(self):
        service = SystemPrinterService()
        with patch.object(service, "check_queue_exists", return_value=False):
            result = service.print_with_pdf_fallback("ticket text", order_id=11, payment_id=21)
        self.assertFalse(result["printed"])
        self.assertIn("/media/receipts/", result["receipt_pdf_url"])
        self.assertTrue(Path(result["receipt_pdf_path"]).exists())

    @override_settings(MEDIA_ROOT=tempfile.gettempdir(), MEDIA_URL="/media/")
    def test_print_with_pdf_fallback_lp_error_generates_pdf(self):
        service = SystemPrinterService()
        with patch.object(service, "check_queue_exists", return_value=True), patch.object(
            service,
            "run_command",
            return_value=CommandResult(ok=False, exit_code=1, stdout="", stderr="Unknown printer", elapsed_ms=5, command="lp -d star_tsp100 /tmp/x"),
        ):
            result = service.print_with_pdf_fallback("ticket text", order_id=12, payment_id=22)
        self.assertFalse(result["printed"])
        self.assertIn("/media/receipts/", result["receipt_pdf_url"])
        self.assertTrue(Path(result["receipt_pdf_path"]).exists())
