from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.cashier.models import CashSession, Register
from apps.cashier.serializers import calculate_shift_summary
from apps.core.models import Branch
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod, Refund
from apps.users.models import UserProfile


class CashReconciliationSummaryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="cash_recon", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.register = Register.objects.create(name="CAJA 1", station_name="POS 1", branch=self.branch, is_active=True)
        self.methods = {
            "cash": PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True),
            "card": PaymentMethod.objects.create(code="card", name="Tarjeta"),
            "transfer": PaymentMethod.objects.create(code="transfer", name="Transferencia"),
            "pedidos_ya": PaymentMethod.objects.create(code="pedidos_ya", name="Pedidos Ya"),
            "paypal": PaymentMethod.objects.create(code="paypal", name="PayPal"),
        }
        self.order_number = 1000

    def _session(self, opening: str = "0.00") -> CashSession:
        return CashSession.objects.create(register=self.register, opened_by=self.user, opening_cash=Decimal(opening), status="open")

    def _order(self, total: str) -> Order:
        self.order_number += 1
        return Order.objects.create(
            order_number=self.order_number,
            branch=self.branch,
            subtotal=Decimal(total),
            tax=Decimal("0.00"),
            total=Decimal(total),
            financial_status="paid",
            payment_status="paid",
        )

    def _payment(self, *, session: CashSession, method_code: str, amount: str) -> Payment:
        method = self.methods[method_code]
        fallback_method = "cash" if method_code == "cash" else ("card" if method_code == "card" else "transfer")
        return Payment.objects.create(
            order=self._order(total=amount),
            payment_method=method,
            method=fallback_method,
            amount=Decimal(amount),
            tip_amount=Decimal("0.00"),
            cash_session=session,
        )

    def _refund(self, *, session: CashSession, payment: Payment, amount: str) -> Refund:
        return Refund.objects.create(
            order=payment.order,
            payment_method=payment.payment_method,
            original_payment=payment,
            cash_session=session,
            method=payment.method if payment.method in {"cash", "card", "transfer"} else "transfer",
            amount=Decimal(amount),
            tip_refunded=Decimal("0.00"),
            reason="Test refund",
            approved_by=self.user,
            created_by=self.user,
        )

    def test_card_sale_adds_positive_bucket(self):
        session = self._session()
        self._payment(session=session, method_code="card", amount="71.19")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["card"], "71.19")

    def test_card_full_refund_same_session_results_net_zero(self):
        session = self._session()
        payment = self._payment(session=session, method_code="card", amount="71.19")
        self._refund(session=session, payment=payment, amount="71.19")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["card"], "0.00")

    def test_cash_full_refund_same_session_updates_cash_and_expected_drawer(self):
        session = self._session(opening="50.00")
        payment = self._payment(session=session, method_code="cash", amount="20.00")
        self._refund(session=session, payment=payment, amount="20.00")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["cash"], "0.00")
        self.assertEqual(summary["total_cash_sales"], "0.00")
        self.assertEqual(summary["expected_cash_in_drawer"], "50.00")

    def test_pedidos_ya_refund_deducts_from_method_bucket(self):
        session = self._session()
        payment = self._payment(session=session, method_code="pedidos_ya", amount="15.40")
        self._refund(session=session, payment=payment, amount="5.40")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["pedidos_ya"], "10.00")

    def test_transfer_refund_deducts_from_method_bucket(self):
        session = self._session()
        payment = self._payment(session=session, method_code="transfer", amount="19.00")
        self._refund(session=session, payment=payment, amount="4.50")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["transfer"], "14.50")

    def test_paypal_refund_deducts_from_method_bucket(self):
        session = self._session()
        payment = self._payment(session=session, method_code="paypal", amount="22.00")
        self._refund(session=session, payment=payment, amount="2.00")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["paypal"], "20.00")

    def test_partial_refund_only_deducts_partial_amount(self):
        session = self._session()
        payment = self._payment(session=session, method_code="card", amount="30.00")
        self._refund(session=session, payment=payment, amount="12.25")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["card"], "17.75")

    def test_mixed_payment_refund_is_applied_per_method(self):
        session = self._session()
        cash_payment = self._payment(session=session, method_code="cash", amount="30.00")
        card_payment = self._payment(session=session, method_code="card", amount="40.00")
        self._refund(session=session, payment=cash_payment, amount="5.00")
        self._refund(session=session, payment=card_payment, amount="15.00")
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["cash"], "25.00")
        self.assertEqual(summary["totals_by_method"]["card"], "25.00")

    def test_refund_in_later_session_keeps_original_sale_and_moves_negative_to_new_session(self):
        session_sale = self._session()
        payment = self._payment(session=session_sale, method_code="card", amount="50.00")
        session_refund = self._session()
        self._refund(session=session_refund, payment=payment, amount="50.00")

        summary_sale = calculate_shift_summary(session_sale)
        summary_refund = calculate_shift_summary(session_refund)
        self.assertEqual(summary_sale["totals_by_method"]["card"], "50.00")
        self.assertEqual(summary_refund["totals_by_method"]["card"], "-50.00")

    def test_refund_retry_does_not_double_discount_when_same_refund_row_is_reprocessed(self):
        session = self._session()
        payment = self._payment(session=session, method_code="card", amount="40.00")
        refund = self._refund(session=session, payment=payment, amount="10.00")
        # Retry path must not create a second refund row for the same refund id.
        refund.refresh_from_db()
        summary = calculate_shift_summary(session)
        self.assertEqual(summary["totals_by_method"]["card"], "30.00")
