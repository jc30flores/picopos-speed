from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.employees.models import Employee
from apps.users.models import UserProfile


class RolePathAccessMiddlewareTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.worker = user_model.objects.create_user(username="worker1", password="123456", is_active=True)
        UserProfile.objects.create(user=self.worker, role="worker", is_active=True)
        Employee.objects.create(full_name="Worker Uno", role="worker", status="active", user=self.worker)

    def _login_worker(self):
        response = self.client.post("/api/auth/login/", {"username": "worker1", "password": "123456"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_worker_can_access_own_attendance_endpoints(self):
        self._login_worker()
        response = self.client.get("/api/employees/attendance/today/")
        self.assertEqual(response.status_code, 200)

    def test_worker_is_blocked_for_other_modules(self):
        self._login_worker()
        response = self.client.get("/api/core/branches/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json().get("detail"), "Sin permisos")
