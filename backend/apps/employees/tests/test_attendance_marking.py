from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch
from apps.employees.models import Employee
from apps.users.models import UserProfile


class AttendanceMarkingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="emp_att", password="123456")
        UserProfile.objects.create(user=user, role="cashier", is_active=True)
        branch = Branch.objects.create(name="Centro", code="CTR")
        self.employee = Employee.objects.create(full_name="Empleado Uno", role="cashier", status="active", user=user, branch=branch)
        self.client.force_authenticate(user)

    def test_today_flow_and_break_rules(self):
        today = self.client.get("/api/employees/attendance/today/")
        self.assertEqual(today.status_code, 200)
        self.assertEqual(today.json().get("state"), "NO_RECORD_TODAY")
        self.assertTrue(today.json()["attendance"]["can_clock_in"])

        clock_in = self.client.post("/api/employees/attendance/clock-in/")
        self.assertEqual(clock_in.status_code, 200)
        self.assertTrue(clock_in.json()["can_break_start"])
        self.assertTrue(clock_in.json()["can_clock_out"])

        break_start = self.client.post("/api/employees/attendance/break-start/")
        self.assertEqual(break_start.status_code, 200)
        self.assertTrue(break_start.json()["can_break_end"])
        self.assertFalse(break_start.json()["can_clock_out"])

        clock_out_invalid = self.client.post("/api/employees/attendance/clock-out/")
        self.assertEqual(clock_out_invalid.status_code, 400)

        break_end = self.client.post("/api/employees/attendance/break-end/")
        self.assertEqual(break_end.status_code, 200)
        self.assertTrue(break_end.json()["can_clock_out"])

        clock_out = self.client.post("/api/employees/attendance/clock-out/")
        self.assertEqual(clock_out.status_code, 200)
        self.assertFalse(clock_out.json()["has_active_session"])
        self.assertTrue(clock_out.json()["can_clock_in"])
        self.assertFalse(clock_out.json()["can_clock_out"])

    def test_multiple_clock_in_clock_out_cycles_same_day(self):
        first_clock_in = self.client.post("/api/employees/attendance/clock-in/")
        self.assertEqual(first_clock_in.status_code, 200)
        self.assertTrue(first_clock_in.json()["has_active_session"])
        self.assertFalse(first_clock_in.json()["can_clock_in"])
        self.assertTrue(first_clock_in.json()["can_clock_out"])

        first_clock_out = self.client.post("/api/employees/attendance/clock-out/")
        self.assertEqual(first_clock_out.status_code, 200)
        self.assertFalse(first_clock_out.json()["has_active_session"])
        self.assertTrue(first_clock_out.json()["can_clock_in"])
        self.assertFalse(first_clock_out.json()["can_clock_out"])

        second_clock_in = self.client.post("/api/employees/attendance/clock-in/")
        self.assertEqual(second_clock_in.status_code, 200)
        self.assertTrue(second_clock_in.json()["has_active_session"])
        self.assertFalse(second_clock_in.json()["can_clock_in"])
        self.assertTrue(second_clock_in.json()["can_clock_out"])

    def test_attendance_endpoints_without_employee_return_200_payload(self):
        self.employee.delete()

        today = self.client.get("/api/employees/attendance/today/")
        self.assertEqual(today.status_code, 200)
        self.assertEqual(today.json(), {"attendance": None, "state": "NO_EMPLOYEE"})

        history = self.client.get("/api/employees/me/attendance/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json(), {"attendance": None, "rows": [], "state": "NO_EMPLOYEE"})

        clock_in = self.client.post("/api/employees/attendance/clock-in/")
        self.assertEqual(clock_in.status_code, 404)
        self.assertEqual(clock_in.json().get("state"), "NO_EMPLOYEE")
