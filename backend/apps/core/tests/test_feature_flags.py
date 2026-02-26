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
