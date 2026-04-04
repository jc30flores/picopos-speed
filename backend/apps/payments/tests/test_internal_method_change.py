from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod, PaymentMethodChangeLog
from apps.users.models import UserProfile


class PaymentInternalMethodChangeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.manager = user_model.objects.create_user(username="manager_method_change", password="123456")
        UserProfile.objects.create(user=self.manager, role="manager", is_active=True)
        self.cashier = user_model.objects.create_user(username="cashier_method_change", password="123456")
        UserProfile.objects.create(user=self.cashier, role="cashier", is_active=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
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

    def test_manager_can_change_internal_payment_method_and_creates_log(self):
        payment = self._create_paid_payment()
        self.client.force_authenticate(self.manager)

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
                changed_by=self.manager,
            ).exists()
        )

    def test_cashier_cannot_change_internal_payment_method(self):
        payment = self._create_paid_payment()
        self.client.force_authenticate(self.cashier)

        response = self.client.patch(
            f"/api/payments/{payment.id}/internal-payment-method/",
            {"payment_method_code": "paypal"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
