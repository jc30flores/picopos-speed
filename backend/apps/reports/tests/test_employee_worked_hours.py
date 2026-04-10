from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.employees.models import AttendanceRecord, Employee
from apps.users.models import UserProfile


class EmployeeWorkedHoursReportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="report_admin", password="pw")
        UserProfile.objects.create(user=user, role="admin", is_active=True)
        self.client.force_authenticate(user)

        self.employee = Employee.objects.create(full_name="Ana López", email="ana@example.com", role="cashier", status="active")

    def test_returns_worked_hours_discounting_breaks(self):
        day = timezone.localdate()
        clock_in = timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=8))
        break_start = clock_in + timedelta(hours=2)
        break_end = break_start + timedelta(minutes=30)
        clock_out = clock_in + timedelta(hours=8)

        AttendanceRecord.objects.create(
            employee=self.employee,
            date=day,
            clock_in=clock_in,
            break_start=break_start,
            break_end=break_end,
            clock_out=clock_out,
            check_in=clock_in,
            check_out=clock_out,
        )

        response = self.client.get(f"/api/reports/employee-worked-hours/?start={day.isoformat()}&end={day.isoformat()}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["employees"]), 1)
        self.assertEqual(response.data["employees"][0]["employee_name"], "Ana López")
        self.assertEqual(response.data["employees"][0]["total_minutes"], 450)
        self.assertEqual(response.data["employees"][0]["total_hours"], "7.50")

    def test_requires_valid_date_range(self):
        day = timezone.localdate().isoformat()
        response = self.client.get(f"/api/reports/employee-worked-hours/?start={day}&end=2020-01-01")
        self.assertEqual(response.status_code, 400)
