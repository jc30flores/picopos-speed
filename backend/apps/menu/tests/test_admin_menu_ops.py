from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Modifier, ModifierGroup, Product
from apps.orders.models import Order, OrderItem


class AdminMenuOpsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin", password="x", role="admin", is_active=True)
        self.client.force_authenticate(user=self.admin)
        self.category = Category.objects.create(name="COMIDA")

    def test_delete_category_with_products_returns_409(self):
        Product.objects.create(name="Item", description="", price=Decimal("1.00"), category=self.category, available=True)
        response = self.client.delete(f"/api/menu/categories/{self.category.id}/")
        self.assertEqual(response.status_code, 409)

    def test_delete_product_with_history_archives(self):
        product = Product.objects.create(name="Item", description="", price=Decimal("2.00"), category=self.category, available=True)
        branch = Branch.objects.create(name="B", code="B")
        service_type = ServiceType.objects.create(key="dine-in", label="En local")
        order = Order.objects.create(order_number=1, branch=branch, service_type=service_type, total=Decimal("2.00"))
        OrderItem.objects.create(order=order, product=product, product_name_snapshot="Item", price_snapshot=Decimal("2.00"), quantity=1)

        response = self.client.delete(f"/api/menu/products/{product.id}/")
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertTrue(product.is_archived)

        list_response = self.client.get("/api/menu/products/")
        self.assertFalse(any(item["id"] == product.id for item in list_response.json()))

    def test_reorder_modifier_group_options(self):
        group = ModifierGroup.objects.create(name="Extras", required=False)
        m1 = Modifier.objects.create(group=group, name="A", price=Decimal("1.00"), sort_order=0)
        m2 = Modifier.objects.create(group=group, name="B", price=Decimal("2.00"), sort_order=1)
        response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/options/reorder/",
            {"ordered_ids": [m2.id, m1.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        m1.refresh_from_db(); m2.refresh_from_db()
        self.assertEqual((m2.sort_order, m1.sort_order), (0, 1))
