from datetime import date
import warnings

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order, OrderInvoice
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


class SalesReportFiltersTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash_report", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_dine = ServiceType.objects.create(key="dine-in", label="DINE IN")
        self.service_takeout = ServiceType.objects.create(key="takeout", label="Takeout")

        self.pm_cash = PaymentMethod.objects.create(code="cash", name="Efectivo", is_cash=True)
        self.pm_paypal = PaymentMethod.objects.create(code="paypal", name="PayPal", is_cash=False)

    def _make_payment(self, *, order_number: int, service_type: ServiceType, payment_method: PaymentMethod, method: str):
        order = Order.objects.create(
            order_number=order_number,
            branch=self.branch,
            service_type=service_type,
            status="delivered",
            customer_name=f"Cliente {order_number}",
            subtotal="10.00",
            tax="1.30",
            total="11.30",
            payment_status="paid",
            financial_status="paid",
            net_paid="11.30",
        )
        OrderInvoice.objects.create(order=order, numero_control=f"DTE-{order_number}")
        Payment.objects.create(order=order, method=method, payment_method=payment_method, amount="11.30", tip_amount="0.00", received_by=self.user)

    def test_requires_date_range(self):
        response = self.client.get("/api/reports/sales/")
        self.assertEqual(response.status_code, 400)

    def test_filter_by_payment_method_and_service_type(self):
        self._make_payment(order_number=1, service_type=self.service_dine, payment_method=self.pm_cash, method="cash")
        self._make_payment(order_number=2, service_type=self.service_takeout, payment_method=self.pm_paypal, method="transfer")

        base_qs = f"date_from={date.today().isoformat()}&date_to={date.today().isoformat()}"
        paypal = self.client.get(f"/api/reports/sales/?{base_qs}&payment_method=paypal")
        self.assertEqual(paypal.status_code, 200)
        self.assertEqual(len(paypal.data["results"]), 1)
        self.assertEqual(paypal.data["results"][0]["payment_method_code"], "paypal")

        dine_cash = self.client.get(f"/api/reports/sales/?{base_qs}&payment_method=cash&service_type=dine_in")
        self.assertEqual(dine_cash.status_code, 200)
        self.assertEqual(len(dine_cash.data["results"]), 1)
        self.assertEqual(dine_cash.data["results"][0]["service_type_code"], "dine_in")
        self.assertEqual(dine_cash.data["results"][0]["payment_method_code"], "cash")

        dine_label = self.client.get(f"/api/reports/sales/?{base_qs}&service_type=DINE IN")
        self.assertEqual(dine_label.status_code, 200)
        self.assertEqual(len(dine_label.data["results"]), 1)

    def test_report_uses_reporting_payment_method_override(self):
        order = Order.objects.create(
            order_number=3,
            branch=self.branch,
            service_type=self.service_dine,
            status="delivered",
            customer_name="Cliente 3",
            subtotal="10.00",
            tax="1.30",
            total="11.30",
            payment_status="paid",
            financial_status="paid",
            net_paid="11.30",
        )
        OrderInvoice.objects.create(order=order, numero_control="DTE-3")
        Payment.objects.create(
            order=order,
            method="cash",
            payment_method=self.pm_cash,
            reporting_payment_method=self.pm_paypal,
            amount="11.30",
            tip_amount="0.00",
            received_by=self.user,
        )

        base_qs = f"date_from={date.today().isoformat()}&date_to={date.today().isoformat()}"
        response = self.client.get(f"/api/reports/sales/?{base_qs}&payment_method=paypal")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["payment_method_code"], "paypal")

    def test_sales_report_date_range_does_not_emit_naive_datetime_warning(self):
        self._make_payment(order_number=10, service_type=self.service_dine, payment_method=self.pm_cash, method="cash")
        base_qs = f"date_from={date.today().isoformat()}&date_to={date.today().isoformat()}"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            response = self.client.get(f"/api/reports/sales/?{base_qs}")
        self.assertEqual(response.status_code, 200)
        warning_messages = [str(item.message) for item in caught]
        self.assertFalse(any("naive datetime" in message.lower() for message in warning_messages))
