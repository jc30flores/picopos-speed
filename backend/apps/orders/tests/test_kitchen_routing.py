from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.serializers import OrderCreateSerializer


class KitchenRoutingTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Sucursal Centro", code="CENTRO")
        self.service_type = ServiceType.objects.create(key="kiosk", label="Kiosk")
        self.pos_service_type = ServiceType.objects.create(key="dine_in", label="Dine in")
        self.category = Category.objects.create(name="BEBIDAS")

    def _create_order(self, product: Product, *, service_type_key: str | None = None):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": service_type_key or self.service_type.key,
                "source": "kiosk" if (service_type_key or self.service_type.key) == self.service_type.key else "pos",
                "channel": "kiosk" if (service_type_key or self.service_type.key) == self.service_type.key else "pos",
                "items": [
                    {
                        "product_id": product.id,
                        "product_name_snapshot": product.name,
                        "price_snapshot": str(product.price),
                        "quantity": 1,
                        "modifiers": [],
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def test_order_requires_kitchen_only_when_any_item_requires_it(self):
        kitchen_product = Product.objects.create(
            name="Burrito",
            description="",
            price=Decimal("8.00"),
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        bar_product = Product.objects.create(
            name="Soda",
            description="",
            price=Decimal("1.50"),
            category=self.category,
            available=True,
            requires_kitchen=False,
        )

        order_kitchen = self._create_order(kitchen_product)
        order_bar = self._create_order(bar_product)

        self.assertTrue(order_kitchen.requires_kitchen)
        self.assertTrue(order_kitchen.send_to_kitchen)
        self.assertFalse(order_bar.requires_kitchen)
        self.assertFalse(order_bar.send_to_kitchen)

    def test_pos_orders_default_to_not_sent_to_kitchen(self):
        kitchen_product = Product.objects.create(
            name="Taco",
            description="",
            price=Decimal("5.00"),
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        pos_order = self._create_order(kitchen_product, service_type_key=self.pos_service_type.key)
        self.assertTrue(pos_order.requires_kitchen)
        self.assertFalse(pos_order.send_to_kitchen)
