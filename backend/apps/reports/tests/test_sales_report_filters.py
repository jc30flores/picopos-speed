from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch
from apps.orders.models import Order, OrderInvoice
from apps.payments.models import Payment
from apps.users.models import UserProfile


class SalesReportFiltersTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash_report", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")

    def _make_paid_order(self, *, order_number: int, customer_name: str, control_number: str) -> Order:
        order = Order.objects.create(
            order_number=order_number,
            branch=self.branch,
            status="delivered",
            customer_name=customer_name,
            subtotal="10.00",
            tax="1.30",
            total="11.30",
            payment_status="paid",
            financial_status="paid",
            net_paid="11.30",
        )
        OrderInvoice.objects.create(order=order, numero_control=control_number)
        Payment.objects.create(order=order, method="cash", amount="11.30", tip_amount="0.00", received_by=self.user)
        return order

    def test_search_matches_customer_and_control_number(self):
        self._make_paid_order(order_number=1, customer_name="Cliente Uno", control_number="DTE-01-M001P001-000000000000001")
        self._make_paid_order(order_number=2, customer_name="Cliente Dos", control_number="DTE-01-M001P001-000000000000002")

        by_customer = self.client.get("/api/reports/sales/?search=Cliente Dos")
        self.assertEqual(by_customer.status_code, 200)
        self.assertEqual(len(by_customer.data["results"]), 1)
        self.assertEqual(by_customer.data["results"][0]["customer_name"], "Cliente Dos")

        by_control = self.client.get("/api/reports/sales/?search=000000000000001")
        self.assertEqual(by_control.status_code, 200)
        self.assertEqual(len(by_control.data["results"]), 1)
        self.assertEqual(by_control.data["results"][0]["control_number"], "DTE-01-M001P001-000000000000001")

    def test_results_include_payment_method_column(self):
        self._make_paid_order(order_number=7, customer_name="Cliente Pago", control_number="DTE-01-M001P001-000000000000007")

        response = self.client.get("/api/reports/sales/?search=Cliente Pago")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["payment_method"], "Cash")
