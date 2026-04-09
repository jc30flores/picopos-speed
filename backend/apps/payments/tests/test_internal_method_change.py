from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cashier.models import CashSession, Register, CashTransaction
from apps.core.models import Branch, ServiceType
from apps.dte.models import DTERecord
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod, PaymentMethodChangeLog, Refund
from apps.users.models import UserProfile


class PaymentInternalMethodChangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="admin_method_change", password="123456")
        UserProfile.objects.create(user=self.admin, role="admin", is_active=True)
        self.manager = user_model.objects.create_user(username="manager_method_change", password="123456")
        UserProfile.objects.create(user=self.manager, role="manager", is_active=True)
        self.cashier = user_model.objects.create_user(username="cashier_method_change", password="123456")
        UserProfile.objects.create(user=self.cashier, role="cashier", is_active=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.register = Register.objects.create(name="Caja Principal", branch=self.branch, is_active=True)
        self.cash_session = CashSession.objects.create(
            register=self.register,
            opened_by=self.admin,
            opening_cash=Decimal("100.00"),
            status="open",
        )
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")
        self.pm_cash = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True)
        self.pm_paypal = PaymentMethod.objects.create(code="paypal", name="PayPal", is_cash=False)

    def _create_paid_payment(self) -> Payment:
        order = Order.objects.create(
            order_number=8000 + Order.objects.count(),
            branch=self.branch,
            service_type=self.service_type,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            financial_status="paid",
        )
        return Payment.objects.create(order=order, method="cash", payment_method=self.pm_cash, amount=Decimal("10.00"))

    def test_admin_can_change_internal_payment_method_and_creates_log(self):
        payment = self._create_paid_payment()
        self.client.force_authenticate(self.admin)

        response = self.client.patch(
            f"/api/payments/{payment.id}/internal-payment-method/",
            {"payment_method_code": "paypal", "reason": "Corrección de cierre"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        payment.refresh_from_db()
        self.assertEqual(payment.reporting_payment_method_id, self.pm_paypal.id)
        self.assertTrue(
            PaymentMethodChangeLog.objects.filter(
                payment=payment,
                old_payment_method=self.pm_cash,
                new_payment_method=self.pm_paypal,
                reason="Corrección de cierre",
                changed_by=self.admin,
            ).exists()
        )

    def test_manager_cannot_change_internal_payment_method(self):
        payment = self._create_paid_payment()
        self.client.force_authenticate(self.manager)
        response = self.client.patch(
            f"/api/payments/{payment.id}/internal-payment-method/",
            {"payment_method_code": "paypal"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_cashier_cannot_change_internal_payment_method(self):
        payment = self._create_paid_payment()
        self.client.force_authenticate(self.cashier)

        response = self.client.patch(
            f"/api/payments/{payment.id}/internal-payment-method/",
            {"payment_method_code": "paypal"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    @patch("apps.payments.views.invalidate_dte_for_order")
    def test_record_refund_cf_invalidates_and_creates_internal_refund(self, mock_invalidate):
        mock_invalidate.return_value = {"success": True}
        payment = self._create_paid_payment()
        DTERecord.objects.create(
            order=payment.order,
            branch=self.branch,
            payment=payment,
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-TEST-1",
            total_amount=Decimal("10.00"),
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/payments/{payment.id}/record-refund/",
            {"reason": "Error en método"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["action"], "invalidate")
        self.assertTrue(Refund.objects.filter(original_payment=payment).exists())
        self.assertTrue(CashTransaction.objects.filter(refund__original_payment=payment, type="cash_out").exists())
        payment.order.refresh_from_db()
        self.assertIn(payment.order.financial_status, {"refunded_partial", "refunded_full"})

    @patch("apps.payments.views.send_dte_for_credit_note")
    def test_record_refund_ccf_after_24h_creates_credit_note(self, mock_send_credit):
        payment = self._create_paid_payment()
        record = DTERecord.objects.create(
            order=payment.order,
            branch=self.branch,
            payment=payment,
            dte_type="CCF_03",
            status=DTERecord.STATUS_ACCEPTED,
            control_number="DTE-TEST-2",
            total_amount=Decimal("10.00"),
        )
        old_ts = timezone.now() - timedelta(hours=25)
        record.recibido_at = old_ts
        record.save(update_fields=["recibido_at"])
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/payments/{payment.id}/record-refund/",
            {"reason": "CCF fuera de ventana"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["action"], "credit_note")
        mock_send_credit.assert_called_once()

    def test_record_refund_without_accepted_dte_creates_internal_refund(self):
        payment = self._create_paid_payment()
        DTERecord.objects.create(
            order=payment.order,
            branch=self.branch,
            payment=payment,
            dte_type="CF_01",
            status=DTERecord.STATUS_REJECTED,
            control_number="DTE-TEST-REJ",
            generation_code="A" * 36,
            total_amount=Decimal("10.00"),
        )
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            f"/api/payments/{payment.id}/record-refund/",
            {"reason": "Sin DTE aceptado"},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["action"], "internal_refund")
        self.assertTrue(Refund.objects.filter(original_payment=payment).exists())
        self.assertTrue(response.data["fiscal_result"]["attempted"])

    @patch("apps.payments.views.invalidate_dte_for_order")
    def test_record_refund_attempts_invalidation_when_latest_dte_rejected(self, mock_invalidate):
        mock_invalidate.return_value = {"success": False, "status": "RECHAZADO", "error": "Documento no anulable"}
        payment = self._create_paid_payment()
        DTERecord.objects.create(
            order=payment.order,
            branch=self.branch,
            payment=payment,
            dte_type="CF_01",
            status=DTERecord.STATUS_REJECTED,
            control_number="DTE-TEST-REJ2",
            generation_code="B" * 36,
            total_amount=Decimal("10.00"),
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"/api/payments/{payment.id}/record-refund/", {"reason": "Reembolso"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["fiscal_result"]["attempted"])
        mock_invalidate.assert_called_once()
