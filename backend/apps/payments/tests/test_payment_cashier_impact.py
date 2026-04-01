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
        self.service_type = ServiceType.objects.create(key="dinein", label="En local")

        self.pm_cash = PaymentMethod.objects.create(code="CASH", name="Efectivo", is_cash=True)
        self.pm_card = PaymentMethod.objects.create(code="CARD", name="Tarjeta", is_cash=False)
        self.pm_pedidosya = PaymentMethod.objects.create(code="PEDIDOS_YA", name="PedidosYa", is_cash=False)
        self.pm_paypal = PaymentMethod.objects.create(code="PAYPAL", name="PayPal", is_cash=False)
        self.pm_transfer = PaymentMethod.objects.create(code="TRANSFER", name="Transferencia", is_cash=False)

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

    def _expected_cash(self) -> Decimal:
        current = self.client.get("/api/cashier/session/current/")
        self.assertEqual(current.status_code, 200)
        return Decimal(str(current.data["summary"]["expected_cash_in_drawer"]))

    def test_cash_payment_increases_cash(self):
        self._open_session("100.00")
        order = self._create_order("10.00")
        response = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "cash", "payment_method": self.pm_cash.id, "amount": "10.00", "tip_amount": "0.00", "cash_received": "10.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        tx = CashTransaction.objects.filter(payment_id=response.data["id"]).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.type, "cash_in")
        self.assertEqual(self._expected_cash(), Decimal("110.00"))

    def test_card_payment_does_not_increase_cash(self):
        self._open_session("100.00")
        order = self._create_order("10.00")
        response = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "card", "payment_method": self.pm_card.id, "amount": "10.00", "tip_amount": "0.00", "card_type": "credit"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        tx = CashTransaction.objects.filter(payment_id=response.data["id"]).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.type, "card")
        self.assertEqual(self._expected_cash(), Decimal("100.00"))

    def test_pedidosya_payment_does_not_increase_cash(self):
        self._open_session("100.00")
        order = self._create_order("10.00")
        response = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "transfer", "payment_method": self.pm_pedidosya.id, "amount": "10.00", "tip_amount": "0.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        tx = CashTransaction.objects.filter(payment_id=response.data["id"]).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.type, "pedidosya")
        self.assertEqual(self._expected_cash(), Decimal("100.00"))

    def test_cash_refund_reduces_cash(self):
        self._open_session("100.00")
        order = self._create_order("10.00")
        pay = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "cash", "payment_method": self.pm_cash.id, "amount": "10.00", "tip_amount": "0.00", "cash_received": "10.00"},
            format="json",
        )
        self.assertEqual(pay.status_code, 201)
        refund = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "original_payment": pay.data["id"],
                "method": "cash",
                "payment_method": self.pm_cash.id,
                "amount": "2.00",
                "tip_refunded": "0.00",
                "reason": "Devolucion",
            },
            format="json",
        )
        self.assertEqual(refund.status_code, 201)
        self.assertEqual(self._expected_cash(), Decimal("108.00"))

    def test_card_refund_does_not_reduce_cash(self):
        self._open_session("100.00")
        order = self._create_order("10.00")
        pay = self.client.post(
            "/api/payments/",
            {"order": order.id, "method": "card", "payment_method": self.pm_card.id, "amount": "10.00", "tip_amount": "0.00", "card_type": "debit"},
            format="json",
        )
        self.assertEqual(pay.status_code, 201)
        refund = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "original_payment": pay.data["id"],
                "method": "card",
                "payment_method": self.pm_card.id,
                "amount": "2.00",
                "tip_refunded": "0.00",
                "reason": "Reverso",
            },
            format="json",
        )
        self.assertEqual(refund.status_code, 201)
        self.assertEqual(self._expected_cash(), Decimal("100.00"))
