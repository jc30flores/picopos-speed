from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.users.models import UserProfile


class FeatureFlagApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role="admin", is_active=True)
        self.worker = get_user_model().objects.create_user(username="worker", password="pass1234")
        UserProfile.objects.create(user=self.worker, role="worker", is_active=True)
        self.client.force_authenticate(user=self.user)

    def test_list_feature_flags(self):
        FeatureFlag.objects.create(
            key="FF_CUSTOMERS_LOYALTY",
            label="Clientes y lealtad",
            description="",
            is_enabled=False,
        )
        response = self.client.get("/api/core/feature-flags/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["key"], "FF_CUSTOMERS_LOYALTY")

    def test_update_feature_flag(self):
        flag = FeatureFlag.objects.create(
            key="FF_SHIFTS_CASH",
            label="Turnos y caja",
            description="",
            is_enabled=False,
        )
        response = self.client.patch(
            f"/api/core/feature-flags/{flag.id}/",
            {"is_enabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        flag.refresh_from_db()
        self.assertTrue(flag.is_enabled)

    def test_settings_features_get_and_patch(self):
        response = self.client.get("/api/settings/features/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("kiosk_enabled", response.data)

        patch = self.client.patch(
            "/api/settings/features/",
            {
                "kiosk_enabled": False,
                "kitchen_display_enabled": False,
                "customer_display_enabled": False,
                "cash_close_expected_totals_allowed_roles": ["cashier"],
                "cash_close_expected_totals_visible_fields": ["expected_cash_in_drawer"],
            },
            format="json",
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data["cash_close_expected_totals_allowed_roles"], ["cashier"])

    def test_settings_features_options_excludes_admin(self):
        response = self.client.get("/api/settings/features/options/")
        self.assertEqual(response.status_code, 200)
        role_codes = [row["code"] for row in response.data["roles"]]
        self.assertNotIn("admin", role_codes)

    def test_worker_can_read_but_cannot_patch_settings_features(self):
        self.client.force_authenticate(user=self.worker)
        read_response = self.client.get("/api/settings/features/")
        self.assertEqual(read_response.status_code, 200)

        patch_response = self.client.patch(
            "/api/settings/features/",
            {"kiosk_enabled": False},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 403)
