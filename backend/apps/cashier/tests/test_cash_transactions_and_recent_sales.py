from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cashier.models import CashSession, CashTransaction, Register
from apps.core.feature_flags import get_pos_quick_sales_settings, set_pos_quick_sales_settings
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

    def _paid_order(self, number=6126, amount="7.28", *, created_at=None, status="delivered", financial_status="paid"):
        order = Order.objects.create(
            order_number=number,
            branch=self.branch,
            service_type=self.service_type,
            total=amount,
            subtotal=amount,
            status=status,
            payment_status="paid",
            financial_status=financial_status,
        )
        payment = Payment.objects.create(order=order, method="cash", payment_method=self.cash_method, amount=amount, amount_applied=amount, cash_session=self.session, received_by=self.cashier)
        if created_at:
            Payment.objects.filter(pk=payment.pk).update(created_at=created_at)
            payment.refresh_from_db()
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

    def test_default_quick_sales_configuration_is_last_sale(self):
        self.assertEqual(get_pos_quick_sales_settings()["mode"], "last_sale")

    def test_last_sale_returns_only_latest_valid_sale_for_cashier(self):
        now = timezone.now()
        self._paid_order(number=1, amount="1.00", created_at=now - timedelta(minutes=3))
        self._paid_order(number=2, amount="2.00", created_at=now - timedelta(minutes=2))
        latest_order, latest_payment = self._paid_order(number=3, amount="3.00", created_at=now - timedelta(minutes=1))
        client = APIClient()
        client.force_authenticate(self.cashier)
        response = client.get(reverse("cashier-last-sale"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], latest_order.id)
        self.assertEqual(response.data["payment_id"], latest_payment.id)

    def test_last_sale_excludes_cancelled_and_fully_refunded_sales(self):
        now = timezone.now()
        valid_order, _ = self._paid_order(number=10, amount="10.00", created_at=now - timedelta(minutes=3))
        self._paid_order(number=11, amount="11.00", created_at=now - timedelta(minutes=2), status="canceled")
        self._paid_order(number=12, amount="12.00", created_at=now - timedelta(minutes=1), financial_status="refunded_full")
        client = APIClient()
        client.force_authenticate(self.cashier)
        response = client.get(reverse("cashier-last-sale"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], valid_order.id)

    def test_recent_sales_requires_history_mode_and_manager_or_admin(self):
        self._paid_order()
        set_pos_quick_sales_settings(mode="history", history_scope="current_shift")
        client = APIClient()
        client.force_authenticate(self.cashier)
        self.assertEqual(client.get(reverse("cashier-recent-sales")).status_code, 403)
        client.force_authenticate(self.manager)
        response = client.get(reverse("cashier-recent-sales"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["payment_id"], Payment.objects.first().id)

    def test_hidden_blocks_quick_sales_endpoints(self):
        self._paid_order()
        set_pos_quick_sales_settings(mode="hidden")
        client = APIClient()
        client.force_authenticate(self.admin)
        self.assertEqual(client.get(reverse("cashier-last-sale")).status_code, 409)
        self.assertEqual(client.get(reverse("cashier-recent-sales")).status_code, 409)

    def test_recent_sales_respects_current_shift(self):
        old_session = CashSession.objects.create(register=self.register, opened_by=self.admin, opening_cash=Decimal("0"), status="closed", closed_at=timezone.now() - timedelta(hours=2))
        old_order, old_payment = self._paid_order(number=20, amount="20.00", created_at=timezone.now() - timedelta(hours=3))
        Payment.objects.filter(pk=old_payment.pk).update(cash_session=old_session)
        self._paid_order(number=21, amount="21.00")
        set_pos_quick_sales_settings(mode="history", history_scope="current_shift")
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get(reverse("cashier-recent-sales"))
        ids = [row["id"] for row in response.data]
        self.assertNotIn(old_order.id, ids)

    def test_recent_sales_respects_time_window(self):
        now = timezone.now()
        old_order, _ = self._paid_order(number=30, amount="30.00", created_at=now - timedelta(minutes=40))
        recent_order, _ = self._paid_order(number=31, amount="31.00", created_at=now - timedelta(minutes=10))
        set_pos_quick_sales_settings(mode="history", history_scope="time_window", history_window_minutes=15)
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.get(reverse("cashier-recent-sales"))
        ids = [row["id"] for row in response.data]
        self.assertIn(recent_order.id, ids)
        self.assertNotIn(old_order.id, ids)
