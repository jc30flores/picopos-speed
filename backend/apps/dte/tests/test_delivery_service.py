from decimal import Decimal
from unittest.mock import patch
import os

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.delivery import deliver_dte_to_client
from apps.dte.services.delivery_config import resolve_delivery_config
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
            {"status": "FAILED", "provider_status": 500, "provider_body": {"error": "http_500", "provider_message": "falló", "to_phone": "50370001111"}},
        )()
        result = deliver_dte_to_client(self.record, channels=("email", "whatsapp"))
        self.assertFalse(result["success"])
        self.assertTrue(result["results"]["email"]["ok"])
        self.assertFalse(result["results"]["whatsapp"]["ok"])
        self.assertEqual(result["results"]["whatsapp"]["provider_status"], 500)
        self.assertEqual(result["results"]["whatsapp"]["provider_message"], "falló")
        self.assertEqual(result["results"]["whatsapp"]["recipient"], "50370001111")

    @override_settings(
        DELIVER_EMAIL_API_BASE_URL="",
        DELIVER_EMAIL_API_ENDPOINT="",
        DELIVER_EMAIL_API_KEY="",
        WHATSAPP_DTE_API_BASE="",
        WHATSAPP_DTE_API_KEY="",
    )
    def test_config_resolves_from_os_environ_when_settings_empty(self):
        with patch.dict(
            os.environ,
            {
                "DELIVER_EMAIL_API_BASE_URL": "https://email.example",
                "DELIVER_EMAIL_API_ENDPOINT": "/api/email/send-invoice",
                "DELIVER_EMAIL_API_KEY": "k1",
                "WHATSAPP_DTE_API_BASE": "https://wa.example",
                "WHATSAPP_DTE_API_KEY": "k2",
            },
            clear=False,
        ):
            cfg = resolve_delivery_config()
            self.assertEqual(cfg.email_base_url, "https://email.example")
            self.assertEqual(cfg.email_url, "https://email.example/api/email/send-invoice")
            self.assertEqual(cfg.whatsapp_base_url, "https://wa.example")
            self.assertEqual(cfg.whatsapp_url, "https://wa.example/api/send-dte-whatsapp")

    @patch("apps.dte.services.delivery.send_dte_email")
    def test_internal_billing_email_is_not_used_for_automatic_email_delivery(self, mock_email):
        self.customer.correo = "facturasPDG23@gmail.com"
        self.customer.save(update_fields=["correo"])
        result = deliver_dte_to_client(self.record, channels=("email",), mode="automatic")
        self.assertFalse(result["success"])
        self.assertIn("interno", (result["results"]["email"]["error"] or "").lower())
        mock_email.assert_not_called()

    @patch("apps.dte.services.delivery.send_dte_email")
    def test_manual_email_override_uses_same_service_with_valid_target(self, mock_email):
        mock_email.return_value = type("Attempt", (), {"status": "SENT", "provider_status": 202, "provider_body": {"provider_message": "queued", "to_email": "cliente.override@example.com"}})()
        self.customer.correo = ""
        self.customer.save(update_fields=["correo"])
        result = deliver_dte_to_client(self.record, channels=("email",), to_email="cliente.override@example.com", mode="manual")
        self.assertTrue(result["success"])
        self.assertEqual(result["results"]["email"]["provider_status"], 202)
        self.assertEqual(result["results"]["email"]["recipient"], "cliente.override@example.com")
        mock_email.assert_called_once()

    def test_invalid_phone_returns_clear_error_and_skips_sender(self):
        self.customer.telefono = "abc"
        self.customer.save(update_fields=["telefono"])
        result = deliver_dte_to_client(self.record, channels=("whatsapp",), mode="manual")
        self.assertFalse(result["success"])
        self.assertIn("inválido", (result["results"]["whatsapp"]["error"] or "").lower())
