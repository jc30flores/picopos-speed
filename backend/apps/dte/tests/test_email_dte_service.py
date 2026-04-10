from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.email_dte_service import send_dte_email, validate_delivery_email_target
from apps.orders.models import Order


class DTEEmailServiceTests(TestCase):
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
            order_number=778,
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
            control_number="DTE-TEST-EMAIL",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            total_amount=Decimal("10.00"),
        )

    def test_validate_email_target_accepts_manual_override_without_customer_email(self):
        self.customer.correo = ""
        self.customer.save(update_fields=["correo"])
        ok, error, email = validate_delivery_email_target(self.record, to_email="override@example.com")
        self.assertTrue(ok)
        self.assertEqual(error, "")
        self.assertEqual(email, "override@example.com")

    @override_settings(DELIVER_EMAIL_API_BASE_URL="https://email.example", DELIVER_EMAIL_API_ENDPOINT="/api/email/send-invoice", DELIVER_EMAIL_API_KEY="k1")
    @patch("apps.dte.services.email_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.email_dte_service.logger")
    @patch("apps.dte.services.email_dte_service.requests.post")
    def test_send_email_logs_provider_body_for_422(self, mock_post, mock_logger, _mock_sleep):
        response = MagicMock()
        response.status_code = 422
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"message": "Validation failed", "errors": {"to_email": ["required"]}}
        response.text = '{"message":"Validation failed","errors":{"to_email":["required"]}}'
        mock_post.return_value = response

        attempt = send_dte_email(self.record, to_email="cliente@example.com")

        self.assertEqual(attempt.status, "FAILED")
        self.assertEqual(attempt.provider_status, 422)
        self.assertEqual(attempt.provider_body.get("provider_message"), "Validation failed")
        self.assertIn("errors", attempt.provider_body)
        self.assertEqual(attempt.provider_body.get("error"), "http_422")
        self.assertTrue(any("provider_422" in str(call) for call in mock_logger.warning.mock_calls))

    @override_settings(DELIVER_EMAIL_API_BASE_URL="https://email.example", DELIVER_EMAIL_API_ENDPOINT="/api/email/send-invoice", DELIVER_EMAIL_API_KEY="k1")
    @patch("apps.dte.services.email_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.email_dte_service.requests.post")
    def test_send_email_uses_invoice_builder_shape(self, mock_post, _mock_sleep):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"message": "sent"}
        response.text = '{"message":"sent"}'
        mock_post.return_value = response

        attempt = send_dte_email(self.record, to_email="cliente@example.com")

        self.assertEqual(attempt.status, "SENT")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["to_email"], "cliente@example.com")
        self.assertEqual(payload["email"], "cliente@example.com")
        self.assertIn("invoice_json", payload)
        self.assertIn("dte_json", payload)
