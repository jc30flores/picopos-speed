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
        self.cashier = user_model.objects.create_user(username="cashier1", password="123456", is_active=True)
        UserProfile.objects.create(user=self.cashier, role="cashier", is_active=True)
        self.manager = user_model.objects.create_user(username="manager1", password="123456", is_active=True)
        UserProfile.objects.create(user=self.manager, role="manager", is_active=True)

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

    def test_cashier_is_blocked_from_reports_api(self):
        self.client.post("/api/auth/login/", {"username": "cashier1", "password": "123456"}, format="json")
        response = self.client.get("/api/reports/sales-timeseries/?start=2026-01-01&end=2026-01-01")
        self.assertEqual(response.status_code, 403)

    def test_manager_is_blocked_from_reportes_and_caja_history_endpoints(self):
        self.client.post("/api/auth/login/", {"username": "manager1", "password": "123456"}, format="json")
        timeseries = self.client.get("/api/reports/sales-timeseries/?start=2026-01-01&end=2026-01-01")
        self.assertEqual(timeseries.status_code, 403)
        breakdown = self.client.get("/api/reports/sales-breakdown/?start=2026-01-01&end=2026-01-01&dimension=category")
        self.assertEqual(breakdown.status_code, 403)
        cash_history = self.client.get("/api/cashier/session/history/")
        self.assertEqual(cash_history.status_code, 403)
