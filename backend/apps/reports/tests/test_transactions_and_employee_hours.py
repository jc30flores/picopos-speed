from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import ServiceType
from apps.core.models import Branch
from apps.employees.models import AttendanceRecord, AttendanceCycle, Employee
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentMethod
from apps.users.models import UserProfile


class ReportTransactionTicketTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="admin2", password="pw")
        UserProfile.objects.create(user=user, role="admin", is_active=True)
        self.client.force_authenticate(user)

    def test_transaction_ticket_endpoint_returns_ticket(self):
        service_type = ServiceType.objects.create(key="DINE_IN", label="Dine In")
        branch = Branch.objects.create(name="Main", code="MAIN")
        order = Order.objects.create(order_number=123, branch=branch, service_type=service_type, total=10, subtotal=8.85, tax=1.15)
        method = PaymentMethod.objects.create(code="cash", name="Efectivo", is_active=True)
        payment = Payment.objects.create(order=order, method="cash", amount=10, payment_method=method)

        response = self.client.get(f"/api/reports/transactions/{payment.id}/ticket/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["payment_id"], payment.id)
        self.assertTrue(response.data["ticket_text"])


class EmployeeHoursReportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="admin3", password="pw")
        UserProfile.objects.create(user=user, role="admin", is_active=True)
        self.client.force_authenticate(user)

        self.employee = Employee.objects.create(full_name="Ana", role="cashier", status="active")
        self.admin_employee = Employee.objects.create(full_name="Root", role="admin", status="active")

    def test_employee_hours_excludes_admin_and_handles_incomplete_cycles(self):
        day = timezone.localdate()
        record = AttendanceRecord.objects.create(employee=self.employee, date=day)
        AttendanceCycle.objects.create(
            attendance_record=record,
            sequence=1,
            clock_in_at=timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=8)),
            break_start_at=timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=10)),
            break_end_at=timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=10, minute=30)),
            clock_out_at=timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=16)),
        )
        AttendanceCycle.objects.create(
            attendance_record=record,
            sequence=2,
            clock_in_at=timezone.make_aware(datetime.combine(day, datetime.min.time()).replace(hour=17)),
        )
        admin_record = AttendanceRecord.objects.create(employee=self.admin_employee, date=day)
        AttendanceCycle.objects.create(
            attendance_record=admin_record,
            sequence=1,
            clock_in_at=timezone.now() - timedelta(hours=1),
            clock_out_at=timezone.now(),
        )

        response = self.client.get(f"/api/reports/employee-hours/?date_from={day.isoformat()}&date_to={day.isoformat()}&group_by=custom")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["employees"]), 1)
        self.assertEqual(response.data["employees"][0]["name"], "Ana")

        detail = self.client.get(f"/api/reports/employee-hours/{self.employee.id}/?date_from={day.isoformat()}&date_to={day.isoformat()}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["days"][0]["cycles"][1]["status"], "en_curso")
