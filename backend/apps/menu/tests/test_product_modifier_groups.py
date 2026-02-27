from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.menu.models import Category, Modifier, ModifierGroup, Product, ProductModifierGroup
from apps.users.models import UserProfile


class ProductModifierGroupPersistenceTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="admin", password="password123")
        UserProfile.objects.create(user=self.user, role="admin", is_active=True)
        self.client.force_authenticate(self.user)

        self.category = Category.objects.create(name="TACOS")
        self.product = Product.objects.create(
            name="Taco al pastor",
            description="Clásico taco al pastor",
            price="12.50",
            category=self.category,
            available=True,
        )
        self.group = ModifierGroup.objects.create(
            name="Tipo de Carne",
            required=False,
            min_selection=0,
            max_selection=2,
        )
        Modifier.objects.create(group=self.group, name="EXTRA", price="1.00", sort_order=0)

    def test_assign_modifier_group_persists_and_returns_on_get(self):
        response = self.client.patch(
            f"/api/menu/products/{self.product.id}/",
            {"modifier_group_ids": [self.group.id]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertIn(self.group, self.product.modifier_groups.all())
        self.assertIn(self.group.id, response.data["modifier_groups"])

        list_response = self.client.get("/api/menu/products/")
        self.assertEqual(list_response.status_code, 200)
        product_payload = next(item for item in list_response.data if item["id"] == self.product.id)
        self.assertIn(self.group.id, product_payload["modifier_groups"])
        self.assertIn(self.group.id, product_payload["modifier_groups_pos"])

    def test_toggle_show_in_pos_updates_product_payload(self):
        ProductModifierGroup.objects.create(product=self.product, modifier_group=self.group, show_in_pos=True)

        response = self.client.patch(
            f"/api/menu/products/{self.product.id}/",
            {
                "modifier_group_ids": [self.group.id],
                "modifier_group_links": [{"group_id": self.group.id, "show_in_pos": False}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn(self.group.id, response.data["modifier_groups_pos"])
        self.assertEqual(
            ProductModifierGroup.objects.get(product=self.product, modifier_group=self.group).show_in_pos,
            False,
        )
