from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.core.models import ServiceType
from apps.menu.models import Category, Product, ProductSpecialPriceRule
from apps.menu.utils.pricing import resolve_effective_price
from apps.users.models import UserProfile


class ProductSpecialPriceRuleTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="admin-special", password="password123")
        UserProfile.objects.create(user=self.user, role="admin", is_active=True)
        self.client.force_authenticate(self.user)

        self.category = Category.objects.create(name="TACOS")
        self.product = Product.objects.create(
            name="Taco promo",
            description="",
            price=Decimal("10.00"),
            category=self.category,
            available=True,
        )
        self.mesa = ServiceType.objects.create(key="MESA", label="Mesa", is_active=True)
        self.para_llevar = ServiceType.objects.create(key="PARA_LLEVAR", label="Para llevar", is_active=True)

    def test_resolve_rule_by_priority_then_best_price(self):
        now = timezone.localtime(timezone.now())
        ProductSpecialPriceRule.objects.create(
            product=self.product,
            name="10%",
            discount_type=ProductSpecialPriceRule.DISCOUNT_TYPE_PERCENT_OFF,
            percent_off=Decimal("10"),
            priority=2,
        )
        ProductSpecialPriceRule.objects.create(
            product=self.product,
            name="20%",
            discount_type=ProductSpecialPriceRule.DISCOUNT_TYPE_PERCENT_OFF,
            percent_off=Decimal("20"),
            priority=2,
        )

        result = resolve_effective_price(self.product, order_type=self.mesa, at=now)
        self.assertEqual(result.effective_price, Decimal("8.00"))
        self.assertEqual(result.applied_rule.name, "20%")

    def test_cross_midnight_window_matches(self):
        rule = ProductSpecialPriceRule.objects.create(
            product=self.product,
            name="Noche",
            discount_type=ProductSpecialPriceRule.DISCOUNT_TYPE_FIXED_PRICE,
            fixed_price=Decimal("6.50"),
            start_time="22:00",
            end_time="02:00",
        )
        rule.order_types.add(self.mesa)
        rule.applies_to_all_order_types = False
        rule.save(update_fields=["applies_to_all_order_types"])

        today = timezone.localdate()
        at = timezone.make_aware(datetime.combine(today, datetime.strptime("01:00", "%H:%M").time()))
        result = resolve_effective_price(self.product, order_type=self.mesa, at=at)
        self.assertEqual(result.effective_price, Decimal("6.50"))
        self.assertEqual(result.applied_rule.id, rule.id)

    def test_delete_order_type_clears_relationship_without_breaking_rule(self):
        rule = ProductSpecialPriceRule.objects.create(
            product=self.product,
            name="Mesa only",
            discount_type=ProductSpecialPriceRule.DISCOUNT_TYPE_PERCENT_OFF,
            percent_off=Decimal("15"),
            applies_to_all_order_types=False,
        )
        rule.order_types.set([self.mesa])

        response = self.client.delete(f"/api/core/order-types/{self.mesa.id}/")
        self.assertEqual(response.status_code, 204)

        rule.refresh_from_db()
        self.assertEqual(rule.order_types.count(), 0)

        result = resolve_effective_price(self.product, order_type=None, at=timezone.now())
        self.assertIsNone(result.applied_rule)
        self.assertEqual(result.effective_price, Decimal("10.00"))
