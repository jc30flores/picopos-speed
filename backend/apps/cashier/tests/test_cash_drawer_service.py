from django.test import SimpleTestCase, override_settings

from apps.cashier.services.cash_drawer import CashDrawerService


class CashDrawerServiceTests(SimpleTestCase):
    @override_settings(CASH_DRAWER_ENABLED=True, CASH_DRAWER_MODE="mock")
    def test_mock_open_drawer_returns_success_without_visible_text(self):
        service = CashDrawerService()
        result = service.open_drawer()
        self.assertTrue(result.success)
        self.assertEqual(result.vendor_id, 0)
        self.assertEqual(result.message, "Gaveta abierta")
        self.assertEqual(service.LEGACY_DRAWER_PRIME_BYTES, b"\n")
