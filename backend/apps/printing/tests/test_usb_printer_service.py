from django.test import SimpleTestCase, override_settings

from apps.printing.services.usb_printer import USBPrinterService


class USBPrinterServiceTests(SimpleTestCase):
    @override_settings(PRINTER_ENABLED=True, RECEIPT_PRINTER_MODE="mock")
    def test_print_receipt_mock_mode(self):
        payload = {
            "text": "ticket",
            "meta": {"type": "customer", "receipt_context": {"order_datetime": None}},
        }
        printed, error = USBPrinterService().print_receipt(payload)
        self.assertTrue(printed)
        self.assertIsNone(error)
