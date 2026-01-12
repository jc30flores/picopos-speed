from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import Order


class KioskOrderCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.branch = Branch.objects.create(name="Sucursal Centro", code="CENTRO")
        self.service_type = ServiceType.objects.create(key="kiosk", label="Kiosk")
        self.category = Category.objects.create(name="BEBIDAS")
        self.product = Product.objects.create(
            name="Agua",
            description="",
            price=Decimal("2.00"),
            category=self.category,
            image=None,
            available=True,
        )

    def test_kiosk_order_creates_preparing_order(self):
        response = self.client.post(
            "/api/orders/",
            {
                "source": "kiosk",
                "channel": "kiosk",
                "service_type_key": "kiosk",
                "items": [
                    {
                        "product_id": self.product.id,
                        "product_name_snapshot": self.product.name,
                        "price_snapshot": "2.00",
                        "quantity": 1,
                        "modifiers": [
                            {"name": "Limón", "price": "0.25"},
                        ],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["status"], "preparing")
        self.assertEqual(payload["service_type"], "kiosk")
        self.assertTrue(payload["order_number"])

        order = Order.objects.get(id=payload["id"])
        self.assertEqual(order.status, "preparing")
