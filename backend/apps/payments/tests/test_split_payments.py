from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import PaymentMethod
from apps.users.models import UserProfile


class SplitPaymentsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="split_cashier", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")
        self.pm_cash = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True)
        self.pm_card = PaymentMethod.objects.create(code="card_debit", name="Tarjeta Débito", is_cash=False)

    def _create_order(self):
        return Order.objects.create(
            order_number=901,
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("22.97"),
            tax=Decimal("0.00"),
            total=Decimal("22.97"),
            amount_due_cents=2297,
        )

    def test_two_part_split_mixed_methods_reaches_zero_remaining(self):
        order = self._create_order()
        first = self.client.post(
            "/api/payments/",
            {
                "order": order.id,
                "method": "card",
                "payment_method": self.pm_card.id,
                "amount": "11.49",
                "amount_applied": "11.49",
                "tip_amount": "0.00",
                "card_type": "debit",
                "split_part": 1,
            },
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            "/api/payments/",
            {
                "order": order.id,
                "method": "cash",
                "payment_method": self.pm_cash.id,
                "amount": "11.48",
                "amount_applied": "11.48",
                "cash_received": "11.48",
                "tip_amount": "0.00",
                "split_part": 2,
            },
            format="json",
        )
        self.assertEqual(second.status_code, 201)
        refreshed = Order.objects.get(pk=order.pk)
        self.assertEqual(refreshed.payment_status, "paid")
        self.assertEqual(refreshed.amount_due_cents, 2297)
