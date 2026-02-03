from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Discount, DiscountRuleTarget, Product
from apps.orders.serializers import OrderCreateSerializer


class DiscountApplicationTests(TestCase):
    def setUp(self) -> None:
        self.branch = Branch.objects.create(name="Sucursal", code="SC1")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.category = Category.objects.create(name="COMIDA")
        self.product_a = Product.objects.create(
            name="Taco",
            description="",
            price="10.00",
            category=self.category,
            available=True,
        )
        self.product_b = Product.objects.create(
            name="Burrito",
            description="",
            price="10.00",
            category=self.category,
            available=True,
        )

    def test_discount_applies_only_to_selected_products(self) -> None:
        discount = Discount.objects.create(
            name="Promo productos",
            description="",
            type="percent",
            value="10.00",
            applies_to="products",
            is_active=True,
            min_amount=None,
            auto_apply=True,
            service_types=[],
            days_of_week=[],
            start_time=None,
            end_time=None,
        )
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_a)

        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "items": [
                    {
                        "product_id": self.product_a.id,
                        "product_name_snapshot": self.product_a.name,
                        "price_snapshot": "10.00",
                        "quantity": 1,
                        "modifiers": [],
                    },
                    {
                        "product_id": self.product_b.id,
                        "product_name_snapshot": self.product_b.name,
                        "price_snapshot": "10.00",
                        "quantity": 1,
                        "modifiers": [],
                    },
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        self.assertEqual(order.discount_total, Decimal("1.00"))
        self.assertEqual(order.applied_discounts.count(), 1)
        self.assertEqual(order.applied_discounts.first().amount_discounted, Decimal("1.00"))
