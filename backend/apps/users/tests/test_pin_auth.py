from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import UserProfile


class PinAuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="cashier1", email="cash1@example.com", password="483921", is_active=True)
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)

    def test_pin_login_success(self):
        response = self.client.post("/api/auth/pin-login/", {"pin": "483921"}, format="json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], "cashier1")

    def test_pin_login_invalid_format_returns_400(self):
        response = self.client.post("/api/auth/pin-login/", {"pin": "12ab"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_pin_login_duplicate_pin_returns_409(self):
        user_model = get_user_model()
        user2 = user_model.objects.create_user(username="cashier2", email="cash2@example.com", password="483921", is_active=True)
        UserProfile.objects.create(user=user2, role="cashier", is_active=True)

        response = self.client.post("/api/auth/pin-login/", {"pin": "483921"}, format="json")
        self.assertEqual(response.status_code, 409)

    def test_pin_login_wrong_pin_returns_401(self):
        response = self.client.post("/api/auth/pin-login/", {"pin": "000000"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_pin_login_accepts_leading_zero_pin(self):
        self.user.set_password("070302")
        self.user.save(update_fields=["password"])
        response = self.client.post("/api/auth/pin-login/", {"pin": "070302"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_pin_login_is_rate_limited_after_5_attempts(self):
        for _ in range(5):
            response = self.client.post("/api/auth/pin-login/", {"pin": "000000"}, format="json")
            self.assertEqual(response.status_code, 401)

        response = self.client.post("/api/auth/pin-login/", {"pin": "000000"}, format="json")
        self.assertEqual(response.status_code, 429)


class AdminPasswordLoginPinFormatTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(username="admin1", email="admin@example.com", password="654321", is_active=True)
        UserProfile.objects.create(user=self.admin, role="admin", is_active=True)

    def test_login_requires_pin_format(self):
        response = self.client.post("/api/auth/login/", {"username": "admin1", "password": "secret"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_login_accepts_6_digit_password(self):
        response = self.client.post("/api/auth/login/", {"username": "admin1", "password": "654321"}, format="json")
        self.assertEqual(response.status_code, 200)
