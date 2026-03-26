from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.dte.models import DTERecord
from apps.dte.services.control import next_control_number
from apps.dte.services.dte_service import interpret_dte_response
from apps.orders.models import Order
from apps.users.models import UserProfile


class DTECoreTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.order = Order.objects.create(
            order_number=1001,
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )

    def test_counter_is_incremental(self):
        first = next_control_number(self.order)
        second = next_control_number(self.order)
        self.assertNotEqual(first, second)

    def test_interpret_dte_response_json_accepted(self):
        parsed = interpret_dte_response(
            {
                "http_status": 200,
                "success": True,
                "respuesta_hacienda": {
                    "estado": "PROCESADO",
                    "selloRecibido": "SELLO-OK",
                    "fhProcesamiento": "2026-01-01T12:00:00",
                },
                "uuid": "abc-uuid",
            }
        )
        self.assertEqual(parsed["status"], DTERecord.STATUS_ACCEPTED)
        self.assertEqual(parsed["sello_recibido"], "SELLO-OK")

    def test_interpret_dte_response_html_502(self):
        parsed = interpret_dte_response({"http_status": 502, "raw": "<html>bad gateway</html>"})
        self.assertEqual(parsed["status"], DTERecord.STATUS_PENDING)
        self.assertIn("html", parsed["response_text"].lower())


class DTEResendEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash2", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        branch = Branch.objects.create(name="Main", code="M2")
        service_type = ServiceType.objects.create(key="takeout", label="Para llevar")
        order = Order.objects.create(order_number=901, branch=branch, service_type=service_type, subtotal=Decimal("2.00"), tax=Decimal("0.00"), total=Decimal("2.00"))
        self.record = DTERecord.objects.create(
            order=order,
            branch=branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_PENDING,
            control_number="DTE-01-M001P001-000000000000001",
            generation_code="A" * 36,
            codigo_generacion="A" * 36,
            send_attempts=0,
            attempts=0,
        )

    @patch("apps.dte.services.dte_retry.send_to_bridge")
    def test_resend_updates_attempts(self, mock_send):
        mock_send.return_value = {"http_status": 200, "success": True, "respuesta_hacienda": {"estado": "PROCESADO"}}
        self.client.force_authenticate(self.user)
        response = self.client.post(f"/api/dte/issued/{self.record.id}/resend/")
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.send_attempts, 1)
        self.assertIn(self.record.status, {DTERecord.STATUS_ACCEPTED, DTERecord.STATUS_PENDING})
