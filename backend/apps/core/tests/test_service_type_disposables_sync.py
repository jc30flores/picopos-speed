from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import ServiceType
from apps.menu.models import Category, Product
from apps.users.models import UserProfile


class ServiceTypeDisposablesSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="admin_disposable", password="pass1234")
        UserProfile.objects.create(user=self.user, role="admin", is_active=True)
        self.client.force_authenticate(user=self.user)

        self.category = Category.objects.create(name="BEBIDAS")
        self.service_type = ServiceType.objects.create(
            key="ONLINE",
            label="Online",
            disposables_enabled=False,
        )
        self.product_one = Product.objects.create(
            name="Soda",
            description="",
            price=1.50,
            category=self.category,
            disposable_apply_to=["ONLINE"],
            available=True,
        )
        self.product_two = Product.objects.create(
            name="Water",
            description="",
            price=1.00,
            category=self.category,
            disposable_apply_to=[],
            available=True,
        )

    def test_turning_off_disposables_removes_service_type_from_all_products(self):
        self.service_type.disposables_enabled = True
        self.service_type.save(update_fields=["disposables_enabled"])

        response = self.client.patch(
            f"/api/core/order-types/{self.service_type.id}/",
            {"disposables_enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.product_one.refresh_from_db()
        self.product_two.refresh_from_db()
        self.assertNotIn(self.service_type.key, self.product_one.disposable_apply_to)
        self.assertNotIn(self.service_type.key, self.product_two.disposable_apply_to)

    def test_turning_on_disposables_applies_service_type_to_all_products(self):
        self.product_one.disposable_apply_to = []
        self.product_one.save(update_fields=["disposable_apply_to"])

        response = self.client.patch(
            f"/api/core/order-types/{self.service_type.id}/",
            {"disposables_enabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.product_one.refresh_from_db()
        self.product_two.refresh_from_db()
        self.assertIn(self.service_type.key, self.product_one.disposable_apply_to)
        self.assertIn(self.service_type.key, self.product_two.disposable_apply_to)


    def test_color_hex_accepts_valid_null_and_repeated_colors(self):
        other = ServiceType.objects.create(key="TAKEOUT", label="Takeout", color_hex="#16A34A")
        response = self.client.patch(
            f"/api/core/order-types/{self.service_type.id}/",
            {"color_hex": "#16a34a"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["color_hex"], "#16A34A")
        other.refresh_from_db()
        self.assertEqual(other.color_hex, "#16A34A")

        response = self.client.patch(
            f"/api/core/order-types/{self.service_type.id}/",
            {"color_hex": None},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["color_hex"])

    def test_color_hex_rejects_invalid_format(self):
        response = self.client.patch(
            f"/api/core/order-types/{self.service_type.id}/",
            {"color_hex": "green"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
