from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.dte.models import DTERecord
from apps.orders.models import Order
from apps.users.models import UserProfile


class DTEPermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)

        branch = Branch.objects.create(name="Main", code="MAIN")
        service_type = ServiceType.objects.create(key="dine-in", label="En local")
        order = Order.objects.create(
            order_number=900,
            branch=branch,
            service_type=service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )
        self.record = DTERecord.objects.create(
            order=order,
            branch=branch,
            dte_type="CF_01",
            status=DTERecord.STATUS_PENDING,
            control_number="CF-MAIN-2026-000000000000001",
            codigo_generacion="A" * 36,
            receiver_name="CF",
            total_amount=Decimal("10.00"),
        )

    def test_list_requires_auth(self):
        res = self.client.get('/api/dte/issued/')
        self.assertIn(res.status_code, [403, 401])

    def test_cashier_can_list(self):
        self.client.force_authenticate(self.user)
        res = self.client.get('/api/dte/issued/')
        self.assertEqual(res.status_code, 200)

    def test_send_email_endpoint_exists(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(f'/api/dte/issued/{self.record.id}/send-email/')
        self.assertIn(res.status_code, [200, 400])

    @patch("apps.dte.views.deliver_dte_to_client")
    def test_send_email_endpoint_uses_shared_delivery_service(self, mock_deliver):
        mock_deliver.return_value = {
            "success": True,
            "order_id": self.record.order_id,
            "issued_id": self.record.id,
            "results": {"email": {"ok": True, "status_code": 200, "error": None}},
            "summary": "ok",
            "mode": "manual",
        }
        self.record.status = DTERecord.STATUS_ACCEPTED
        self.record.save(update_fields=["status"])
        self.client.force_authenticate(self.user)
        res = self.client.post(f"/api/dte/issued/{self.record.id}/send-email/", {"email": "cliente@example.com"}, format="json")
        self.assertEqual(res.status_code, 200)
        mock_deliver.assert_called_once()

    @patch("apps.dte.views.deliver_dte_to_client")
    def test_send_whatsapp_endpoint_uses_shared_delivery_service(self, mock_deliver):
        mock_deliver.return_value = {
            "success": True,
            "order_id": self.record.order_id,
            "issued_id": self.record.id,
            "results": {"whatsapp": {"ok": True, "status_code": 200, "error": None}},
            "summary": "ok",
            "mode": "manual",
        }
        self.record.status = DTERecord.STATUS_ACCEPTED
        self.record.save(update_fields=["status"])
        self.client.force_authenticate(self.user)
        res = self.client.post(f"/api/dte/issued/{self.record.id}/send-whatsapp/", {"phone": "50370001111"}, format="json")
        self.assertEqual(res.status_code, 200)
        mock_deliver.assert_called_once()
