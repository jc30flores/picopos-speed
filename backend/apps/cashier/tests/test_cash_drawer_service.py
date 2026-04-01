from django.test import SimpleTestCase, override_settings

from apps.cashier.services.cash_drawer import CashDrawerService


class CashDrawerServiceTests(SimpleTestCase):
    @override_settings(CASH_DRAWER_ENABLED=True, CASH_DRAWER_MODE="mock")
    def test_mock_open_drawer_returns_success_without_test_line(self):
        service = CashDrawerService()
        result = service.open_drawer()
        self.assertEqual(result.vendor_id, 0)
        self.assertFalse(hasattr(service, "TEST_LINE"))
