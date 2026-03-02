from decimal import Decimal
from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.dte.services.dte_numbers import next_control_number


class DTENumbersTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")

    def test_counter_increments(self):
        order = Order.objects.create(order_number=1, branch=self.branch, service_type=self.service_type, subtotal=Decimal('1.00'), tax=Decimal('0.00'), total=Decimal('1.00'))
        n1 = next_control_number(order)
        n2 = next_control_number(order)
        self.assertNotEqual(n1, n2)
