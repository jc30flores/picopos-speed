from django.test import TestCase

from apps.core.models import Branch, Customer, ServiceType
from apps.dte.services.customer_rules import is_consumer_final_order
from apps.orders.models import Order


class CustomerRulesTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine_in", label="En local")

    def _build_order(self, *, is_consumer_final: bool, client_type: str, dte_document_type: str = "CF") -> Order:
        customer = Customer.objects.create(
            name="Cliente",
            full_name="Cliente",
            client_type=client_type,
            is_consumer_final=is_consumer_final,
        )
        return Order.objects.create(
            order_number=700 + Customer.objects.count(),
            branch=self.branch,
            service_type=self.service_type,
            customer=customer,
            customer_name="Cliente",
            dte_document_type=dte_document_type,
            status="waiting_payment",
            payment_status="paid",
            subtotal="10.00",
            tax="0.00",
            total="10.00",
        )

    def test_detects_consumer_final_by_flag(self):
        order = self._build_order(is_consumer_final=True, client_type="CF")
        self.assertTrue(is_consumer_final_order(order))

    def test_detects_non_consumer_final_by_client_type(self):
        order = self._build_order(is_consumer_final=False, client_type="CCF", dte_document_type="CCF")
        self.assertFalse(is_consumer_final_order(order))
