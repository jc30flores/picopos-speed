from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import DTEGlobalSettings, FeatureFlag
from apps.users.models import UserProfile


class FeatureFlagApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="admin", password="pass1234")
        UserProfile.objects.create(user=self.user, role="admin", is_active=True)
        self.superadmin = get_user_model().objects.create_user(username="superadmin", password="pass1234")
        UserProfile.objects.create(user=self.superadmin, role="superadmin", is_active=True)
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
        self.client.force_authenticate(user=self.superadmin)
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
        self.client.force_authenticate(user=self.superadmin)
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
        self.client.force_authenticate(user=self.superadmin)
        response = self.client.get("/api/settings/features/options/")
        self.assertEqual(response.status_code, 200)
        role_codes = [row["code"] for row in response.data["roles"]]
        self.assertNotIn("admin", role_codes)

    def test_worker_cannot_read_or_patch_settings_features(self):
        self.client.force_authenticate(user=self.worker)
        read_response = self.client.get("/api/settings/features/")
        self.assertEqual(read_response.status_code, 403)

        patch_response = self.client.patch(
            "/api/settings/features/",
            {"kiosk_enabled": False},
            format="json",
        )
        self.assertEqual(patch_response.status_code, 403)

    def test_settings_appearance_get_and_patch(self):
        response = self.client.get("/api/settings/appearance/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("css_variables", response.data)

        patch = self.client.patch("/api/settings/appearance/", {"primary_color": "#2563EB"}, format="json")
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data["primary_color"], "#2563EB")
        self.assertIn("--color-primary", patch.data["css_variables"])

        neutral = self.client.patch("/api/settings/appearance/", {"primary_color": "#374151"}, format="json")
        self.assertEqual(neutral.status_code, 200)
        self.assertIn("--color-primary-on-light", neutral.data["css_variables"])

        invalid = self.client.patch("/api/settings/appearance/", {"primary_color": "blue"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data["error"], "invalid_color_format")
        self.assertIn("suggestions", invalid.data)

    def test_settings_dte_get_and_superadmin_only_technical_patch(self):
        response = self.client.get("/api/settings/dte/")
        self.assertEqual(response.status_code, 403)

        admin_patch = self.client.patch("/api/settings/dte/", {"base_url": "https://example.test/api"}, format="json")
        self.assertEqual(admin_patch.status_code, 403)

        self.client.force_authenticate(user=self.superadmin)
        super_get = self.client.get("/api/settings/dte/")
        self.assertEqual(super_get.status_code, 200)
        self.assertFalse(super_get.data["enabled"])
        self.assertEqual(super_get.data["config_status"], DTEGlobalSettings.STATUS_DISABLED)
        super_patch = self.client.patch(
            "/api/settings/dte/",
            {"enabled": False, "environment": "test", "base_url": "https://example.test/api", "api_token": "secret-token"},
            format="json",
        )
        self.assertEqual(super_patch.status_code, 200)
        self.assertEqual(super_patch.data["base_url"], "https://example.test/api")
        self.assertIn("issuer", super_patch.data)
        self.assertIn("branch", super_patch.data)
        self.assertIn("permissions", super_patch.data)
        self.assertNotIn("secret-token", str(super_patch.data))
