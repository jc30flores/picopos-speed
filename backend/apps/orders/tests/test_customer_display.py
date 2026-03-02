from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem


class CustomerDisplayOrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.category = Category.objects.create(name="ALMUERZO")
        self.product = Product.objects.create(
            name="Plato Test",
            description="",
            price=Decimal("10.00"),
            category=self.category,
            image=None,
            available=True,
        )

    def test_customer_display_empty(self):
        response = self.client.get("/api/orders/customer-display/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_customer_display_returns_orders(self):
        order = Order.objects.create(
            order_number=100,
            branch=self.branch,
            service_type=self.service_type,
            status="new",
            customer_name="Maria",
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name_snapshot=self.product.name,
            price_snapshot=self.product.price,
            quantity=1,
        )

        response = self.client.get("/api/orders/customer-display/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["order_number"], 100)

    def test_customer_board_only_returns_preparing_and_ready(self):
        Order.objects.create(
            order_number=101,
            branch=self.branch,
            service_type=self.service_type,
            status="new",
            customer_name="Hidden",
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        preparing = Order.objects.create(
            order_number=102,
            branch=self.branch,
            service_type=self.service_type,
            status="preparing",
            customer_name="Prep",
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )
        ready = Order.objects.create(
            order_number=103,
            branch=self.branch,
            service_type=self.service_type,
            status="ready",
            customer_name="Ready",
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
            discount_total=Decimal("0.00"),
        )

        response = self.client.get("/api/orders/customer-board/")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["order_number"] for item in payload], [preparing.order_number, ready.order_number])
