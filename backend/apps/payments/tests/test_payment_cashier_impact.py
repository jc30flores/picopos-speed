from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cashier.models import CashTransaction
from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import PaymentMethod
from apps.users.models import UserProfile


class PaymentCashierImpactTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="manager_cash_impact", password="pw")
        UserProfile.objects.create(user=self.user, role="manager", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")

        self.pm_cash = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True)
        self.pm_card_credit = PaymentMethod.objects.create(code="card_credit", name="Tarjeta Crédito", is_cash=False)
        self.pm_transfer = PaymentMethod.objects.create(code="transfer", name="Transferencia", is_cash=False)

    def _open_session(self, opening_cash: str = "100.00"):
        self.client.post("/api/cashier/session/open/", {"opening_cash_amount": opening_cash}, format="json")

    def _create_order(self, total: str = "10.00") -> Order:
        return Order.objects.create(
            order_number=5000 + Order.objects.count(),
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal(total),
            tax=Decimal("0.00"),
            total=Decimal(total),
        )

    def test_non_cash_payments_do_not_create_cash_transactions(self):
        self._open_session("100.00")
        order = self._create_order("10.00")
        response = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "card", "payment_method": self.pm_card_credit.id, "amount": "10.00", "tip_amount": "0.00", "card_type": "credit"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(CashTransaction.objects.filter(payment_id=response.data["id"]).exists())

    def test_expected_cash_only_uses_cash_movements(self):
        self._open_session("100.00")
        order_cash = self._create_order("10.00")
        order_card = self._create_order("20.00")
        order_transfer = self._create_order("15.00")

        cash_payment = self.client.post(
            "/api/payments/",
            {"order": order_cash.id, "method": "cash", "payment_method": self.pm_cash.id, "amount": "10.00", "tip_amount": "0.00", "cash_received": "10.00"},
            format="json",
        )
        self.assertEqual(cash_payment.status_code, 201)

        self.client.post(
            "/api/payments/",
            {"order": order_card.id, "method": "card", "payment_method": self.pm_card_credit.id, "amount": "20.00", "tip_amount": "0.00", "card_type": "credit"},
            format="json",
        )
        self.client.post(
            "/api/payments/",
            {"order": order_transfer.id, "method": "transfer", "payment_method": self.pm_transfer.id, "amount": "15.00", "tip_amount": "0.00"},
            format="json",
        )

        self.client.post("/api/cashier/transactions/", {"type": "cash_out", "amount": "5.00", "description": "Mercado"}, format="json")

        current = self.client.get("/api/cashier/session/current/")
        self.assertEqual(current.status_code, 200)
        summary = current.data["summary"]
        self.assertEqual(Decimal(summary["opening_cash"]), Decimal("100.00"))
        self.assertEqual(Decimal(summary["total_cash_sales"]), Decimal("10.00"))
        self.assertEqual(Decimal(summary["cash_expenses_total"]), Decimal("5.00"))
        self.assertEqual(Decimal(summary["expected_cash_in_drawer"]), Decimal("105.00"))
        self.assertEqual(Decimal(summary["totals_by_method"]["card_credit"]), Decimal("20.00"))
        self.assertEqual(Decimal(summary["totals_by_method"]["transfer"]), Decimal("15.00"))
        self.assertTrue(all(row["description"] == "Mercado" for row in summary["cash_movements"]))
