from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.users.models import UserProfile


class PaymentDteTriggerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash3", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        branch = Branch.objects.create(name="Main", code="M3")
        service_type = ServiceType.objects.create(key="drive", label="Drive")
        self.order = Order.objects.create(
            order_number=777,
            branch=branch,
            service_type=service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )

    @patch("apps.payments.views.send_dte_for_order")
    def test_no_dte_when_payment_create_fails(self, mock_send):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/payments/",
            {"order": self.order.id, "method": "cash", "amount": "100.00", "tip_amount": "0.00", "cash_received": "100.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        mock_send.assert_not_called()
