from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import PaymentMethod
from apps.users.models import UserProfile


class PaymentMethodResolutionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="cash_pm_resolution", password="123456")
        UserProfile.objects.create(user=user, role="cashier", is_active=True)
        self.client.force_authenticate(user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="pos", label="POS")
        self.order = Order.objects.create(
            order_number=6100,
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )

    def test_create_payment_accepts_card_code_when_only_legacy_card_method_exists(self):
        PaymentMethod.objects.create(code="card_credit", name="Tarjeta Crédito", is_cash=False, is_active=True)

        response = self.client.post(
            "/api/payments/",
            {
                "order": self.order.id,
                "method": "card",
                "payment_method_code": "card",
                "amount": "10.00",
                "tip_amount": "0.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data.get("method"), "card")

    def test_create_payment_accepts_tarjeta_alias(self):
        PaymentMethod.objects.create(code="card_debit", name="Tarjeta Débito", is_cash=False, is_active=True)

        response = self.client.post(
            "/api/payments/",
            {
                "order": self.order.id,
                "method": "card",
                "payment_method_code": "tarjeta",
                "amount": "10.00",
                "tip_amount": "0.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data.get("method"), "card")

    def test_payment_methods_endpoint_collapses_legacy_card_codes_into_single_card_entry(self):
        PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True, is_active=True)
        PaymentMethod.objects.create(code="card_credit", name="Tarjeta Crédito", is_cash=False, is_active=True)
        PaymentMethod.objects.create(code="card_debit", name="Tarjeta Débito", is_cash=False, is_active=True)
        PaymentMethod.objects.create(code="transfer", name="Transferencia", is_cash=False, is_active=True)

        response = self.client.get("/api/payments/methods/")

        self.assertEqual(response.status_code, 200, response.data)
        card_entries = [row for row in response.data if str(row.get("code")).lower() == "card"]
        self.assertEqual(len(card_entries), 1, response.data)
