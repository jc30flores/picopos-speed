from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cashier.models import CashSession, CashTransaction, Register
from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile
from apps.cashier.serializers import calculate_shift_summary


class CashTransactionsAndRecentSalesTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Sucursal", code="SUC")
        self.register = Register.objects.create(name="Caja", branch=self.branch)
        self.admin = User.objects.create_user("admin", password="x")
        self.manager = User.objects.create_user("manager", password="x")
        self.cashier = User.objects.create_user("cashier", password="x")
        UserProfile.objects.create(user=self.admin, role="admin", is_active=True)
        UserProfile.objects.create(user=self.manager, role="manager", is_active=True)
        UserProfile.objects.create(user=self.cashier, role="cashier", is_active=True)
        self.session = CashSession.objects.create(register=self.register, opened_by=self.admin, opening_cash=Decimal("20.00"))
        self.service_type = ServiceType.objects.create(key="DINE_IN", label="Restaurante")
        self.cash_method = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True, fiscal_payment_type="CASH")

    def _paid_order(self, number=6126, amount="7.28"):
        order = Order.objects.create(order_number=number, branch=self.branch, service_type=self.service_type, total=amount, subtotal=amount, payment_status="paid")
        payment = Payment.objects.create(order=order, method="cash", payment_method=self.cash_method, amount=amount, amount_applied=amount, cash_session=self.session, received_by=self.cashier)
        CashTransaction.objects.create(session=self.session, type="cash_out", amount=amount, description=f"Pago efectivo orden #{number}", payment=payment, created_by=self.cashier)
        return order, payment

    def test_order_payment_cash_transaction_is_not_manual_expense(self):
        self._paid_order()
        CashTransaction.objects.create(session=self.session, type="cash_out", amount="3.00", description="Pago proveedor", created_by=self.cashier)
        summary = calculate_shift_summary(self.session)
        self.assertEqual(summary["cash_expenses_total"], "3.00")
        self.assertEqual(summary["expected_cash_in_drawer"], "24.28")
        self.assertEqual(len(summary["cash_movements"]), 1)
        self.assertEqual(summary["cash_movements"][0]["description"], "Pago proveedor")

    def test_transactions_endpoint_excludes_order_payments_even_when_cashier_bug_exists(self):
        self._paid_order()
        CashTransaction.objects.create(session=self.session, type="cash_out", amount="3.00", description="Pago proveedor", created_by=self.cashier)
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get(reverse("cashier-transactions"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["description"] for row in response.data], ["Pago proveedor"])

    def test_recent_sales_requires_manager_or_admin(self):
        self._paid_order()
        client = APIClient()
        client.force_authenticate(self.cashier)
        self.assertEqual(client.get(reverse("cashier-recent-sales")).status_code, 403)
        client.force_authenticate(self.manager)
        response = client.get(reverse("cashier-recent-sales"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["payment_id"], Payment.objects.first().id)
