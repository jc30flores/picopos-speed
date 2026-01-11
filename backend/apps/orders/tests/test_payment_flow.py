from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem


class OrderPaymentFlowTests(TestCase):
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

    def test_order_waiting_payment_then_preparing_on_payment(self):
        order = Order.objects.create(
            order_number=101,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            customer_name="",
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

        response = self.client.post(
            "/api/payments/",
            {
                "order": order.id,
                "method": "cash",
                "amount": "10.00",
                "tip_amount": "0.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        order.refresh_from_db()
        self.assertEqual(order.status, "preparing")
