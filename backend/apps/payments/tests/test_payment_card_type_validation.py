from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.users.models import UserProfile


class PaymentCardTypeValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="cash_pay", password="123456")
        UserProfile.objects.create(user=user, role="cashier", is_active=True)
        self.client.force_authenticate(user)
        branch = Branch.objects.create(name="Main", code="MAIN")
        service_type = ServiceType.objects.create(key="pos", label="POS")
        self.order = Order.objects.create(
            order_number=5001,
            branch=branch,
            service_type=service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )

    def test_card_payment_defaults_to_single_card_type(self):
        response = self.client.post(
            "/api/payments/",
            {
                "order": self.order.id,
                "method": "card",
                "amount": "10.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data.get("card_type"), "credit")
