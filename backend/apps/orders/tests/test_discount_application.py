from decimal import Decimal
from unittest.mock import patch
from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Discount, DiscountRuleTarget, Modifier, ModifierGroup, Product
from apps.orders.discount_engine import discount_business_weekday, discount_conditions_met
from apps.orders.serializers import OrderCreateSerializer
from apps.orders.services.totals import calculate_order_totals


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

    def _build_order_serializer(self, *, discount_id: int | None = None, manual_discount_snapshot: dict | None = None):
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
            payload["manual_discount_id"] = discount_id
            payload["discount_mode"] = "manual"
        if manual_discount_snapshot is not None:
            payload["manual_discount_snapshot"] = manual_discount_snapshot
        return OrderCreateSerializer(data=payload)

    def test_order_manual_discount_no_conditions_applies(self):
        discount = Discount.objects.create(
            name="Manual 10%",
            type="percent",
            value="10.00",
            applies_to="order",
            is_active=True,
            auto_apply=False,
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

    def test_order_manual_discount_ignores_conditions(self):
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

    def test_order_discount_snapshot_saved(self):
        discount = Discount.objects.create(
            name="Manual fijo",
            type="fixed",
            value="2.50",
            applies_to="order",
            is_active=True,
            auto_apply=False,
        )
        serializer = self._build_order_serializer(
            discount_id=discount.id,
            manual_discount_snapshot={"name": "override", "amount_applied": "999.00"},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        self.assertEqual(order.discount_total, Decimal("2.50"))
        self.assertEqual(order.discount_snapshot.get("name"), "Manual fijo")
        self.assertEqual(order.discount_snapshot.get("amount"), "2.50")
        self.assertEqual(order.discount_snapshot.get("manual_input", {}).get("name"), "override")

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


class AutomaticDiscountEligibilityTests(TestCase):
    def setUp(self) -> None:
        self.branch = Branch.objects.create(name="Sucursal descuentos", code="DISC-AUTO")
        self.mesa_service = ServiceType.objects.create(key="MESA", label="Mesa")
        self.delivery_service = ServiceType.objects.create(key="DELIVERY", label="Delivery")
        self.category = Category.objects.create(name="MARISCOS AUTO")
        self.shrimp = Product.objects.create(
            name="Camarones empanizados",
            description="",
            price=Decimal("5.99"),
            category=self.category,
            available=True,
        )
        self.crepe = Product.objects.create(
            name="Crepa de Melocoton",
            description="",
            price=Decimal("4.00"),
            category=self.category,
            available=True,
        )
        self.water = Product.objects.create(
            name="Agua mineral",
            description="",
            price=Decimal("2.00"),
            category=self.category,
            available=True,
        )

    def _student_discount(self, *, days=None, service_types=None, start=None, end=None, products=None, min_amount=Decimal("0.00")) -> Discount:
        discount = Discount.objects.create(
            name="DESCUENTO ESTUDIANTE",
            type="percent",
            value=Decimal("25.00"),
            applies_to="products",
            is_active=True,
            auto_apply=True,
            days_of_week=[1, 2, 3, 4, 5, 6] if days is None else days,
            start_time=time(11, 0) if start is None else start,
            end_time=time(14, 0) if end is None else end,
            service_types=["MESA"] if service_types is None else service_types,
            min_amount=min_amount,
        )
        for product in products or [self.shrimp]:
            DiscountRuleTarget.objects.create(discount=discount, product=product)
        return discount

    def _capture_payload(self, *, service_type_key="MESA", shrimp_quantity=1, include_crepe=True, product=None):
        items = []
        if include_crepe:
            items.append(
                {
                    "product_id": self.crepe.id,
                    "product_name_snapshot": self.crepe.name,
                    "price_snapshot": "4.00",
                    "quantity": 3,
                    "modifiers": [],
                }
            )
        selected_product = product or self.shrimp
        items.append(
            {
                "product_id": selected_product.id,
                "product_name_snapshot": selected_product.name,
                "price_snapshot": str(selected_product.price),
                "quantity": shrimp_quantity,
                "modifiers": [],
            }
        )
        return {
            "branch_id": self.branch.id,
            "service_type_key": service_type_key,
            "items": items,
        }

    def _save_order_at(self, local_dt: datetime, payload: dict):
        with patch("apps.orders.discount_engine.timezone.now", return_value=local_dt):
            serializer = OrderCreateSerializer(data=payload)
            self.assertTrue(serializer.is_valid(), serializer.errors)
            return serializer.save()

    def test_weekday_mapping_uses_visual_d_l_m_x_j_v_s_values(self) -> None:
        base_sunday = timezone.make_aware(datetime(2026, 7, 26, 13, 0, 0))
        for expected_day in range(7):
            local_dt = base_sunday + timedelta(days=expected_day)
            self.assertEqual(discount_business_weekday(local_dt), expected_day)
            discount = Discount(
                name=f"Dia {expected_day}",
                type="percent",
                value=Decimal("10.00"),
                applies_to="order",
                is_active=True,
                auto_apply=True,
                days_of_week=[expected_day],
                service_types=["MESA"],
                start_time=time(11, 0),
                end_time=time(14, 0),
                min_amount=Decimal("0.00"),
            )
            self.assertTrue(
                discount_conditions_met(
                    discount,
                    service_type_key="MESA",
                    now=local_dt,
                    subtotal_before_discounts=Decimal("1.00"),
                )
            )
            discount.days_of_week = [(expected_day + 1) % 7]
            self.assertFalse(
                discount_conditions_met(
                    discount,
                    service_type_key="MESA",
                    now=local_dt,
                    subtotal_before_discounts=Decimal("1.00"),
                )
            )

    def test_capture_case_applies_to_selected_product_only(self) -> None:
        self._student_discount()
        local_dt = timezone.make_aware(datetime(2026, 7, 27, 13, 16, 0))

        order = self._save_order_at(local_dt, self._capture_payload())
        items = list(order.items.order_by("id"))
        totals = calculate_order_totals(order)

        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.discount_snapshot.get("name"), "DESCUENTO ESTUDIANTE")
        self.assertEqual(order.discount_snapshot.get("mode"), "auto")
        self.assertTrue(order.discount_snapshot.get("conditions_met"))
        self.assertEqual(totals.subtotal, Decimal("17.99"))
        self.assertEqual(totals.discount_total, Decimal("1.50"))
        self.assertEqual(totals.total, Decimal("16.49"))
        self.assertEqual(order.discount_total, Decimal("1.50"))
        self.assertEqual(order.total, Decimal("16.49"))
        self.assertEqual(order.amount_due_cents, 1649)
        self.assertEqual(items[0].product_id, self.crepe.id)
        self.assertEqual(items[0].discount_amount, Decimal("0.00"))
        self.assertEqual(items[1].product_id, self.shrimp.id)
        self.assertEqual(items[1].discount_amount, Decimal("1.50"))

    def test_sunday_does_not_apply_for_monday_to_saturday_rule(self) -> None:
        self._student_discount()
        local_dt = timezone.make_aware(datetime(2026, 8, 2, 13, 16, 0))

        order = self._save_order_at(local_dt, self._capture_payload())

        self.assertEqual(order.discount_total, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("17.99"))
        self.assertEqual(order.amount_due_cents, 1799)

    def test_time_window_boundaries_are_local_and_inclusive(self) -> None:
        self._student_discount()
        expectations = [
            (datetime(2026, 7, 27, 10, 59, 0), Decimal("0.00"), Decimal("17.99")),
            (datetime(2026, 7, 27, 11, 0, 0), Decimal("1.50"), Decimal("16.49")),
            (datetime(2026, 7, 27, 13, 16, 0), Decimal("1.50"), Decimal("16.49")),
            (datetime(2026, 7, 27, 14, 0, 0), Decimal("1.50"), Decimal("16.49")),
            (datetime(2026, 7, 27, 14, 1, 0), Decimal("0.00"), Decimal("17.99")),
        ]

        for raw_dt, discount_total, total in expectations:
            order = self._save_order_at(timezone.make_aware(raw_dt), self._capture_payload())
            self.assertEqual(order.discount_total, discount_total, raw_dt)
            self.assertEqual(order.total, total, raw_dt)

    def test_time_window_crossing_midnight_uses_local_time(self) -> None:
        self._student_discount(days=[1, 2, 3, 4, 5, 6], start=time(22, 0), end=time(2, 0))
        inside_late = self._save_order_at(timezone.make_aware(datetime(2026, 7, 27, 23, 30, 0)), self._capture_payload())
        inside_early = self._save_order_at(timezone.make_aware(datetime(2026, 7, 28, 1, 30, 0)), self._capture_payload())
        outside = self._save_order_at(timezone.make_aware(datetime(2026, 7, 28, 3, 0, 0)), self._capture_payload())

        self.assertEqual(inside_late.discount_total, Decimal("1.50"))
        self.assertEqual(inside_early.discount_total, Decimal("1.50"))
        self.assertEqual(outside.discount_total, Decimal("0.00"))

    def test_service_type_must_match_stable_key(self) -> None:
        self._student_discount()
        local_dt = timezone.make_aware(datetime(2026, 7, 27, 13, 16, 0))

        delivery_order = self._save_order_at(local_dt, self._capture_payload(service_type_key="DELIVERY"))
        mesa_order = self._save_order_at(local_dt, self._capture_payload(service_type_key="MESA"))

        self.assertEqual(delivery_order.discount_total, Decimal("0.00"))
        self.assertEqual(delivery_order.total, Decimal("17.99"))
        self.assertEqual(mesa_order.discount_total, Decimal("1.50"))
        self.assertEqual(mesa_order.total, Decimal("16.49"))

    def test_unselected_product_does_not_receive_discount(self) -> None:
        self._student_discount()
        local_dt = timezone.make_aware(datetime(2026, 7, 27, 13, 16, 0))

        order = self._save_order_at(local_dt, self._capture_payload(include_crepe=False, product=self.water))

        self.assertEqual(order.discount_total, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("2.00"))
        self.assertEqual(order.items.first().discount_amount, Decimal("0.00"))

    def test_quantity_uses_line_subtotal_and_half_up_money_rounding(self) -> None:
        self._student_discount()
        local_dt = timezone.make_aware(datetime(2026, 7, 27, 13, 16, 0))

        order = self._save_order_at(local_dt, self._capture_payload(include_crepe=False, shrimp_quantity=2))

        self.assertEqual(order.discount_total, Decimal("3.00"))
        self.assertEqual(order.total, Decimal("8.98"))
        self.assertEqual(order.amount_due_cents, 898)
        self.assertEqual(order.items.first().discount_amount, Decimal("3.00"))
