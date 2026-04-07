from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.delivery import deliver_dte_to_client
from apps.orders.models import Order


class DTEDeliveryServiceTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")
        self.customer = Customer.objects.create(
            nombre="Cliente",
            correo="cliente@example.com",
            telefono="50370001111",
            tipo_cliente="CF",
        )
        self.order = Order.objects.create(
            order_number=777,
            branch=self.branch,
            service_type=self.service_type,
            customer=self.customer,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )
        self.record = DTERecord.objects.create(
            order=self.order,
            branch=self.branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-TEST-DELIVERY",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            total_amount=Decimal("10.00"),
        )

    @override_settings(
        DELIVER_EMAIL_API_BASE_URL="",
        EMAIL_API_BASE_URL="",
        DELIVER_EMAIL_API_KEY="",
        EMAIL_API_KEY="",
        WHATSAPP_DTE_API_BASE="",
        WHATSAPP_DTE_API_KEY="",
    )
    def test_missing_config_returns_channel_errors_and_no_global_success(self):
        result = deliver_dte_to_client(self.record, channels=("email", "whatsapp"))
        self.assertFalse(result["success"])
        self.assertIn("email", result["results"])
        self.assertIn("whatsapp", result["results"])
        self.assertEqual(result["results"]["email"]["error"], "DELIVER_EMAIL_API_BASE_URL missing")
        self.assertEqual(result["results"]["whatsapp"]["error"], "WHATSAPP_DTE_API_BASE missing")

    @patch("apps.dte.services.delivery.send_dte_email")
    @patch("apps.dte.services.delivery.send_dte_whatsapp")
    def test_partial_channel_failure_keeps_success_false(self, mock_whatsapp, mock_email):
        mock_email.return_value = type("Attempt", (), {"status": "SENT", "provider_status": 200, "provider_body": {}})()
        mock_whatsapp.return_value = type(
            "Attempt",
            (),
            {"status": "FAILED", "provider_status": 500, "provider_body": {"error": "http_500"}},
        )()
        result = deliver_dte_to_client(self.record, channels=("email", "whatsapp"))
        self.assertFalse(result["success"])
        self.assertTrue(result["results"]["email"]["ok"])
        self.assertFalse(result["results"]["whatsapp"]["ok"])
