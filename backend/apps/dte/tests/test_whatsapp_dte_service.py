from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.whatsapp_dte_service import build_whatsapp_payload, send_dte_whatsapp, validate_whatsapp_target
from apps.orders.models import Order


class DTEWhatsAppServiceTests(TestCase):
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
            order_number=779,
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
            control_number="DTE-TEST-WA",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            total_amount=Decimal("10.00"),
        )

    @override_settings(WHATSAPP_DEFAULT_TO_PHONE="50370000000")
    def test_build_whatsapp_payload_uses_gateway_contract(self):
        payload = build_whatsapp_payload(self.record)
        self.assertEqual(payload["num_receptor"], "50370000000")
        self.assertTrue(payload["send_json"])
        self.assertEqual(payload["tipo_dte"], "01")
        self.assertEqual(payload["doc_type"], "CF")
        self.assertIn("descripcion_msg", payload)

    def test_validate_whatsapp_target_rejects_invalid_number(self):
        ok, error, phone = validate_whatsapp_target(self.record, to_phone="abc")
        self.assertFalse(ok)
        self.assertIn("inválido", error.lower())
        self.assertEqual(phone, "")

    @override_settings(WHATSAPP_DTE_API_BASE="https://wa.example", WHATSAPP_DTE_API_KEY="k1")
    @patch("apps.dte.services.whatsapp_dte_service.time.sleep", return_value=None)
    @patch("apps.dte.services.whatsapp_dte_service.requests.post")
    def test_send_whatsapp_uses_same_builder_shape(self, mock_post, _mock_sleep):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"message": "queued"}
        response.text = '{"message":"queued"}'
        mock_post.return_value = response

        attempt = send_dte_whatsapp(self.record, to_phone="50379998888")

        self.assertEqual(attempt.status, "SENT")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["num_receptor"], "50379998888")
        self.assertIn("dte", payload)
        self.assertTrue(payload["send_json"])
