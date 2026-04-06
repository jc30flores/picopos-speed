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
        self.admin = user_model.objects.create_user(username="admin_pin", email="admin_pin@example.com", password="654321", is_active=True)
        UserProfile.objects.create(user=self.admin, role="admin", is_active=True)
        self.manager = user_model.objects.create_user(username="manager_pin", email="manager_pin@example.com", password="123456", is_active=True)
        UserProfile.objects.create(user=self.manager, role="manager", is_active=True)
        self.client.force_authenticate(self.user)

    def test_pin_login_success(self):
        response = self.client.post("/api/auth/pin-login/", {"pin": "483921"}, format="json")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["username"], "cashier1")
        self.assertEqual(payload["redirect_to"], "/")

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

    def test_authorize_price_change_accepts_admin_or_manager_pin(self):
        admin_response = self.client.post("/api/auth/authorize-price-change/", {"pin": "654321"}, format="json")
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json().get("ok"), True)

        manager_response = self.client.post("/api/auth/authorize-price-change/", {"pin": "123456"}, format="json")
        self.assertEqual(manager_response.status_code, 200)
        self.assertEqual(manager_response.json().get("ok"), True)

    def test_authorize_price_change_rejects_cashier_pin_with_generic_message(self):
        response = self.client.post("/api/auth/authorize-price-change/", {"pin": "483921"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("detail"), "Código inválido")

    def test_authorize_price_change_rejects_invalid_format_with_generic_message(self):
        response = self.client.post("/api/auth/authorize-price-change/", {"pin": "1111"}, format="json")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("detail"), "Código inválido")


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

    def test_pin_login_returns_role_landing_redirect(self):
        user_model = get_user_model()
        kitchen = user_model.objects.create_user(username="kitchen1", password="112233", is_active=True)
        UserProfile.objects.create(user=kitchen, role="kitchen", is_active=True)
        response = self.client.post("/api/auth/pin-login/", {"pin": "112233"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("redirect_to"), "/kitchen")


class SessionAuthFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="pin_session", password="012345", is_active=True)
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)

    def _ensure_csrf(self):
        csrf_response = self.client.get("/api/auth/csrf/")
        self.assertEqual(csrf_response.status_code, 200)
        token = self.client.cookies.get("csrftoken")
        self.assertIsNotNone(token)
        return token.value

    def test_pin_login_success_sets_session(self):
        token = self._ensure_csrf()
        response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", self.client.cookies)

    def test_me_requires_auth_and_works_after_login(self):
        unauth = self.client.get("/api/auth/me/")
        self.assertEqual(unauth.status_code, 401)

        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json().get("username"), "pin_session")

    def test_logout_works_with_csrf(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)

        logout_token = self._ensure_csrf()
        logout_response = self.client.post("/api/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=logout_token)
        self.assertEqual(logout_response.status_code, 204)
