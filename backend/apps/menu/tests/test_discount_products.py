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


    def test_bxgy_requires_rules(self) -> None:
        serializer = DiscountSerializer(
            data={
                "name": "BOGO",
                "description": "",
                "type": "bxgy",
                "value": "0",
                "applies_to": "order",
                "is_active": True,
                "min_amount": None,
                "auto_apply": True,
                "service_types": [],
                "days_of_week": [],
                "start_time": None,
                "end_time": None,
                "bxgy_config": {},
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("bxgy_config", serializer.errors)

    def test_bxgy_valid_config_passes(self) -> None:
        serializer = DiscountSerializer(
            data={
                "name": "BOGO",
                "description": "",
                "type": "bxgy",
                "value": "0",
                "applies_to": "order",
                "is_active": True,
                "min_amount": None,
                "auto_apply": True,
                "service_types": [],
                "days_of_week": [],
                "start_time": None,
                "end_time": None,
                "bxgy_config": {
                    "rules": [
                        {
                            "id": "r1",
                            "buy": {"qty": 2, "selector": {"mode": "products", "product_ids": [self.product.id], "category_ids": []}},
                            "get": {
                                "qty": 1,
                                "selector": {"mode": "products", "product_ids": [self.product.id], "category_ids": []},
                                "reward": {"type": "percent", "value": 100},
                                "apply_to": "cheapest",
                            },
                            "limits": {"max_applications_per_ticket": 1},
                        }
                    ],
                    "global": {"exclude_disposables": True, "overlap_buy_get": False},
                },
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
