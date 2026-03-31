from decimal import Decimal
from unittest.mock import patch
from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Discount, DiscountRuleTarget, Modifier, ModifierGroup, Product
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
        self.beverage_category = Category.objects.create(name="BEBIDAS")
        self.product_c = Product.objects.create(
            name="Soda",
            description="",
            price="5.00",
            category=self.beverage_category,
            available=True,
        )

    def _build_order_serializer(self, *, discount_id: int | None = None):
        payload = {
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
        if discount_id is not None:
            payload["discount_id"] = discount_id
            payload["discount_mode"] = "manual"
        return OrderCreateSerializer(data=payload)

    def test_discount_without_conditions_does_not_auto_apply_but_manual_applies(self):
        discount = Discount.objects.create(
            name="Manual 10%",
            type="percent",
            value="10.00",
            applies_to="order",
            is_active=True,
            auto_apply=True,
            service_types=[],
            days_of_week=[],
            start_time=None,
            end_time=None,
            min_amount=None,
        )
        auto_serializer = self._build_order_serializer()
        self.assertTrue(auto_serializer.is_valid(), auto_serializer.errors)
        auto_order = auto_serializer.save()
        self.assertEqual(auto_order.discount_total, Decimal("0.00"))

        manual_serializer = self._build_order_serializer(discount_id=discount.id)
        self.assertTrue(manual_serializer.is_valid(), manual_serializer.errors)
        manual_order = manual_serializer.save()
        self.assertEqual(manual_order.discount_total, Decimal("2.00"))
        self.assertEqual(manual_order.discount_snapshot.get("discount_id"), discount.id)
        self.assertEqual(manual_order.items.filter(discount_amount__gt=0).count(), 2)

    def test_manual_discount_applies_even_outside_conditions(self):
        discount = Discount.objects.create(
            name="Solo lunes",
            type="percent",
            value="10.00",
            applies_to="order",
            is_active=True,
            auto_apply=True,
            service_types=[],
            days_of_week=[0],
            start_time=None,
            end_time=None,
            min_amount=None,
        )
        fake_now = timezone.make_aware(datetime(2026, 3, 31, 12, 0, 0))  # Tuesday
        with patch("apps.orders.discount_engine.timezone.now", return_value=fake_now):
            serializer = self._build_order_serializer(discount_id=discount.id)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("2.00"))
        self.assertFalse(order.discount_snapshot.get("conditions_met"))

    def test_discount_applies_only_to_selected_products(self) -> None:
        discount = Discount.objects.create(
            name="Promo productos",
            description="",
            type="percent",
            value="10.00",
            applies_to="products",
            is_active=True,
            min_amount=Decimal("1.00"),
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

    def test_auto_discount_with_conditions_applies_without_manual_selection(self):
        discount = Discount.objects.create(
            name="Auto con condición",
            type="fixed",
            value="3.00",
            applies_to="order",
            is_active=True,
            min_amount=Decimal("10.00"),
            auto_apply=True,
        )
        serializer = self._build_order_serializer()
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("3.00"))
        self.assertEqual(order.discount_snapshot.get("discount_id"), discount.id)

    def test_bxgy_same_product_deterministic(self) -> None:
        discount = Discount.objects.create(
            name="2x1 Taco",
            description="",
            type="bxgy",
            value="0.00",
            applies_to="products",
            is_active=True,
            auto_apply=True,
            bxgy_config={
                "rules": [
                    {
                        "id": "r1",
                        "buy": {"qty": 2, "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []}},
                        "get": {
                            "qty": 1,
                            "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []},
                            "reward": {"type": "percent", "value": 100},
                            "apply_to": "cheapest",
                        },
                        "limits": {"max_applications_per_ticket": 2},
                    }
                ],
                "global": {"exclude_disposables": True, "overlap_buy_get": False},
            },
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
                        "quantity": 6,
                        "modifiers": [],
                    },
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("20.00"))

    def test_bxgy_cross_category(self) -> None:
        discount = Discount.objects.create(
            name="Compra 2 tacos lleva soda",
            description="",
            type="bxgy",
            value="0.00",
            applies_to="order",
            is_active=True,
            auto_apply=True,
            bxgy_config={
                "rules": [
                    {
                        "id": "r1",
                        "buy": {"qty": 2, "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []}},
                        "get": {
                            "qty": 1,
                            "selector": {"mode": "products", "product_ids": [self.product_c.id], "category_ids": []},
                            "reward": {"type": "percent", "value": 100},
                            "apply_to": "cheapest",
                        },
                        "limits": {"max_applications_per_ticket": 1},
                    }
                ],
                "global": {"exclude_disposables": True, "overlap_buy_get": False},
            },
        )
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_a)
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_c)

        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "items": [
                    {"product_id": self.product_a.id, "product_name_snapshot": self.product_a.name, "price_snapshot": "10.00", "quantity": 2, "modifiers": []},
                    {"product_id": self.product_c.id, "product_name_snapshot": self.product_c.name, "price_snapshot": "5.00", "quantity": 1, "modifiers": []},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("5.00"))

    def test_bxgy_without_get_item_does_not_apply(self) -> None:
        discount = Discount.objects.create(
            name="Compra 2 tacos lleva soda",
            description="",
            type="bxgy",
            value="0.00",
            applies_to="order",
            is_active=True,
            auto_apply=True,
            bxgy_config={
                "rules": [
                    {
                        "id": "r1",
                        "buy": {"qty": 2, "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []}},
                        "get": {
                            "qty": 1,
                            "selector": {"mode": "products", "product_ids": [self.product_c.id], "category_ids": []},
                            "reward": {"type": "percent", "value": 100},
                            "apply_to": "cheapest",
                        },
                        "limits": {"max_applications_per_ticket": 1},
                    }
                ],
            },
        )
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_a)

        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "items": [
                    {"product_id": self.product_a.id, "product_name_snapshot": self.product_a.name, "price_snapshot": "10.00", "quantity": 2, "modifiers": []},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("0.00"))

    def test_bxgy_including_paid_modifiers(self) -> None:
        group = ModifierGroup.objects.create(name="EXTRAS", required=False)
        extra = Modifier.objects.create(group=group, name="QUESO", price=Decimal("2.00"), sort_order=0)
        self.product_a.modifier_groups.add(group)

        discount = Discount.objects.create(
            name="BOGO con extras",
            description="",
            type="bxgy",
            value="0.00",
            applies_to="products",
            is_active=True,
            auto_apply=True,
            bxgy_config={
                "rules": [
                    {
                        "id": "r1",
                        "buy": {"qty": 1, "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []}},
                        "get": {
                            "qty": 1,
                            "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []},
                            "reward": {"type": "percent", "value": 100, "include_paid_modifiers": True},
                            "apply_to": "cheapest",
                            "include_paid_modifiers": True,
                        },
                        "limits": {"max_applications_per_ticket": 1},
                    }
                ],
            },
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
                        "quantity": 2,
                        "modifiers": [{"id": extra.id}],
                    },
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("12.00"))

    def test_discount_time_window_crossing_midnight(self) -> None:
        discount = Discount.objects.create(
            name="Nocturno",
            description="",
            type="percent",
            value="10.00",
            applies_to="order",
            is_active=True,
            auto_apply=True,
            service_types=[self.service_type.key],
            days_of_week=[0, 1, 2, 3, 4, 5, 6],
            start_time="22:00",
            end_time="02:00",
        )
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_a)

        fake_now = timezone.make_aware(datetime(2026, 1, 10, 1, 0, 0))
        with patch("apps.orders.discount_engine.timezone.now", return_value=fake_now):
            serializer = OrderCreateSerializer(
                data={
                    "branch_id": self.branch.id,
                    "service_type_key": self.service_type.key,
                    "items": [
                        {"product_id": self.product_a.id, "product_name_snapshot": self.product_a.name, "price_snapshot": "10.00", "quantity": 1, "modifiers": []},
                    ],
                }
            )
            self.assertTrue(serializer.is_valid(), serializer.errors)
            order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("1.00"))

    def test_bxgy_same_pool_qty_three_applies_once(self) -> None:
        discount = Discount.objects.create(
            name="2+1 taco",
            description="",
            type="bxgy",
            value="0.00",
            applies_to="products",
            is_active=True,
            auto_apply=True,
            bxgy_config={
                "rules": [
                    {
                        "id": "r1",
                        "mode": "same_pool",
                        "buy": {"qty": 2, "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []}},
                        "get": {
                            "qty": 1,
                            "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []},
                            "reward": {"type": "percent", "value": 100},
                            "apply_to": "cheapest",
                        },
                        "limits": {"max_applications_per_ticket": 5},
                    }
                ],
            },
        )
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_a)
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "items": [
                    {"product_id": self.product_a.id, "product_name_snapshot": self.product_a.name, "price_snapshot": "10.00", "quantity": 3, "modifiers": []},
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.discount_total, Decimal("10.00"))

    def test_bxgy_separate_pool_deterministic_order(self) -> None:
        discount = Discount.objects.create(
            name="Compra taco lleva soda",
            description="",
            type="bxgy",
            value="0.00",
            applies_to="order",
            is_active=True,
            auto_apply=True,
            bxgy_config={
                "rules": [
                    {
                        "id": "r1",
                        "mode": "separate_pool",
                        "buy": {"qty": 2, "selector": {"mode": "products", "product_ids": [self.product_a.id], "category_ids": []}},
                        "get": {
                            "qty": 1,
                            "selector": {"mode": "products", "product_ids": [self.product_c.id], "category_ids": []},
                            "reward": {"type": "percent", "value": 100},
                            "apply_to": "cheapest",
                        },
                        "limits": {"max_applications_per_ticket": 2},
                    }
                ],
            },
        )
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_a)
        DiscountRuleTarget.objects.create(discount=discount, product=self.product_c)

        payload_a = {
            "branch_id": self.branch.id,
            "service_type_key": self.service_type.key,
            "items": [
                {"product_id": self.product_a.id, "product_name_snapshot": self.product_a.name, "price_snapshot": "10.00", "quantity": 2, "modifiers": []},
                {"product_id": self.product_c.id, "product_name_snapshot": self.product_c.name, "price_snapshot": "5.00", "quantity": 1, "modifiers": []},
            ],
        }
        payload_b = {
            "branch_id": self.branch.id,
            "service_type_key": self.service_type.key,
            "items": [
                {"product_id": self.product_c.id, "product_name_snapshot": self.product_c.name, "price_snapshot": "5.00", "quantity": 1, "modifiers": []},
                {"product_id": self.product_a.id, "product_name_snapshot": self.product_a.name, "price_snapshot": "10.00", "quantity": 2, "modifiers": []},
            ],
        }

        serializer_a = OrderCreateSerializer(data=payload_a)
        serializer_b = OrderCreateSerializer(data=payload_b)
        self.assertTrue(serializer_a.is_valid(), serializer_a.errors)
        self.assertTrue(serializer_b.is_valid(), serializer_b.errors)
        order_a = serializer_a.save()
        order_b = serializer_b.save()

        self.assertEqual(order_a.discount_total, Decimal("5.00"))
        self.assertEqual(order_b.discount_total, Decimal("5.00"))
