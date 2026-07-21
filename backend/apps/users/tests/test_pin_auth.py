from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.session_security import SESSION_LAST_ACTIVITY_KEY, SESSION_LOGIN_AT_KEY
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
        session = self.client.session
        self.assertIsNotNone(session.get(SESSION_LOGIN_AT_KEY))
        self.assertIsNotNone(session.get(SESSION_LAST_ACTIVITY_KEY))

    def test_me_requires_auth_and_works_after_login(self):
        unauth = self.client.get("/api/auth/me/")
        self.assertEqual(unauth.status_code, 401)

        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json().get("username"), "pin_session")

    def test_authenticated_request_updates_last_activity_inside_limits(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)
        session = self.client.session
        previous_activity = int(timezone.now().timestamp()) - 30
        session[SESSION_LAST_ACTIVITY_KEY] = previous_activity
        session.save()

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        refreshed_session = self.client.session
        self.assertGreaterEqual(refreshed_session[SESSION_LAST_ACTIVITY_KEY], previous_activity)

    def test_idle_timeout_expires_backend_session(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)
        session = self.client.session
        session[SESSION_LAST_ACTIVITY_KEY] = int(timezone.now().timestamp()) - 601
        session.save()

        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("code"), "idle_timeout")
        self.assertEqual(response.json().get("detail"), "Tu sesión se cerró por inactividad.")

    def test_absolute_session_age_expires_even_with_recent_activity(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)
        session = self.client.session
        now = int(timezone.now().timestamp())
        session[SESSION_LOGIN_AT_KEY] = now - 43201
        session[SESSION_LAST_ACTIVITY_KEY] = now
        session.save()

        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("code"), "max_session_age")
        self.assertEqual(response.json().get("detail"), "Tu sesión venció por seguridad. Ingresa nuevamente.")

    def test_week_old_session_is_not_accepted(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)
        session = self.client.session
        now = int(timezone.now().timestamp())
        session[SESSION_LOGIN_AT_KEY] = now - 7 * 24 * 60 * 60
        session[SESSION_LAST_ACTIVITY_KEY] = now
        session.save()

        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json().get("code"), "max_session_age")

    def test_public_endpoint_does_not_require_session_security(self):
        response = self.client.get("/api/public/pwa/metadata/")
        self.assertEqual(response.status_code, 200)

    def test_pin_login_and_me_return_stable_contract(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)
        payload = login_response.json()
        self.assertIn("user", payload)
        self.assertIn("profile", payload)
        self.assertEqual(payload["user"]["username"], "pin_session")

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        me_payload = me_response.json()
        self.assertEqual(me_payload["user"]["username"], "pin_session")
        self.assertEqual(me_payload["profile"]["role"], "cashier")
        self.assertIn("permissions", me_payload)

    def test_pin_login_creates_session_and_me_works_with_same_client(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)
        self.assertTrue(login_response["Content-Type"].startswith("application/json"))
        self.assertIn("sessionid", self.client.cookies)

        me_response = self.client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["user"]["username"], "pin_session")

    def test_logout_works_with_csrf(self):
        token = self._ensure_csrf()
        login_response = self.client.post("/api/auth/pin-login/", {"pin": "012345"}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(login_response.status_code, 200)

        logout_token = self._ensure_csrf()
        logout_response = self.client.post("/api/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=logout_token)
        self.assertEqual(logout_response.status_code, 204)

    def test_logout_is_idempotent_when_no_active_session(self):
        token = self._ensure_csrf()
        response = self.client.post("/api/auth/logout/", {}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 204)
