from django.test import TestCase

from apps.menu.models import Category, Product
from apps.menu.serializers import DiscountSerializer


class DiscountProductValidationTests(TestCase):
    def setUp(self) -> None:
        self.category = Category.objects.create(name="BEBIDAS")
        self.product = Product.objects.create(
            name="Cafe",
            description="",
            price="3.50",
            category=self.category,
            available=True,
        )

    def test_requires_products_when_applies_to_products(self) -> None:
        serializer = DiscountSerializer(
            data={
                "name": "Promo",
                "description": "",
                "type": "percent",
                "value": "10",
                "applies_to": "products",
                "is_active": True,
                "min_amount": None,
                "auto_apply": True,
                "service_types": [],
                "days_of_week": [],
                "start_time": None,
                "end_time": None,
                "target_product_ids": [],
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("target_product_ids", serializer.errors)

    def test_accepts_valid_products_when_applies_to_products(self) -> None:
        serializer = DiscountSerializer(
            data={
                "name": "Promo",
                "description": "",
                "type": "percent",
                "value": "10",
                "applies_to": "products",
                "is_active": True,
                "min_amount": None,
                "auto_apply": True,
                "service_types": [],
                "days_of_week": [],
                "start_time": None,
                "end_time": None,
                "target_product_ids": [self.product.id],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
