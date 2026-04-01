from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cashier.models import CashTransaction
from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod, Refund
from apps.payments.views import _create_cash_out_for_refund
from apps.users.models import UserProfile


class RefundCashierIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="manager_refund", password="pw")
        UserProfile.objects.create(user=self.user, role="manager", is_active=True)
        self.client.force_authenticate(self.user)

        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dinein", label="En local")
        self.cash_method = PaymentMethod.objects.create(code="CASH", name="Efectivo", is_cash=True)
        self.card_method = PaymentMethod.objects.create(code="CARD", name="Tarjeta", is_cash=False)

    def _open_session(self, opening_cash: str = "100.00"):
        return self.client.post("/api/cashier/session/open/", {"opening_cash_amount": opening_cash}, format="json")

    def _create_order_and_payment(self, *, method: str, payment_method: PaymentMethod, amount: str = "10.00"):
        order = Order.objects.create(
            order_number=1000 + Order.objects.count(),
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal(amount),
            tax=Decimal("0.00"),
            total=Decimal(amount),
        )
        payment = Payment.objects.create(
            order=order,
            method=method,
            payment_method=payment_method,
            amount=Decimal(amount),
            tip_amount=Decimal("0.00"),
            received_by=self.user,
        )
        order.recalculate_financials()
        return order, payment

    def test_cash_refund_creates_cash_out_and_reduces_expected_cash(self):
        self._open_session("100.00")
        order, payment = self._create_order_and_payment(method="cash", payment_method=self.cash_method, amount="10.00")

        response = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "original_payment": payment.id,
                "method": "cash",
                "payment_method": self.cash_method.id,
                "amount": "2.00",
                "tip_refunded": "0.00",
                "reason": "Cliente devolvió producto",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        refund_id = response.data["refund"]["id"]
        tx = CashTransaction.objects.filter(refund_id=refund_id).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.type, "cash_out")
        self.assertEqual(tx.amount, Decimal("2.00"))

        current = self.client.get("/api/cashier/session/current/")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(Decimal(str(current.data["summary"]["expected_cash_in_drawer"])), Decimal("108.00"))

    def test_card_refund_does_not_create_cash_transaction(self):
        self._open_session("100.00")
        order, payment = self._create_order_and_payment(method="card", payment_method=self.card_method, amount="10.00")

        response = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "original_payment": payment.id,
                "method": "card",
                "payment_method": self.card_method.id,
                "amount": "2.00",
                "tip_refunded": "0.00",
                "reason": "Reverso tarjeta",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertFalse(CashTransaction.objects.filter(refund_id=response.data["refund"]["id"]).exists())

    def test_same_refund_cash_out_creation_is_idempotent(self):
        self._open_session("100.00")
        order, payment = self._create_order_and_payment(method="cash", payment_method=self.cash_method, amount="10.00")
        refund = Refund.objects.create(
            order=order,
            original_payment=payment,
            cash_session=self.user.opened_cash_sessions.filter(status="open").first(),
            method="cash",
            payment_method=self.cash_method,
            amount=Decimal("1.50"),
            tip_refunded=Decimal("0.00"),
            reason="Test idempotencia",
            approved_by=self.user,
            created_by=self.user,
        )

        first, created_first = _create_cash_out_for_refund(refund, self.user)
        second, created_second = _create_cash_out_for_refund(refund, self.user)

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.id, second.id)
        self.assertEqual(CashTransaction.objects.filter(refund=refund).count(), 1)

    def test_cash_refund_without_open_session_returns_400(self):
        order, payment = self._create_order_and_payment(method="cash", payment_method=self.cash_method, amount="10.00")

        response = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "original_payment": payment.id,
                "method": "cash",
                "payment_method": self.cash_method.id,
                "amount": "2.00",
                "tip_refunded": "0.00",
                "reason": "Sin caja abierta",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data.get("detail"), "No hay caja abierta para registrar el reembolso.")

    def test_refund_validation_errors_are_returned_clearly(self):
        self._open_session("100.00")
        order, payment = self._create_order_and_payment(method="cash", payment_method=self.cash_method, amount="10.00")
        response = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "original_payment": payment.id,
                "method": "cash",
                "payment_method": self.cash_method.id,
                "amount": "0.00",
                "tip_refunded": "0.00",
                "reason": "",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.data)
