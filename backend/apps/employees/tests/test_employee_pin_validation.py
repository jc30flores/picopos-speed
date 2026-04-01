from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import serializers

from apps.employees.models import Employee
from apps.employees.serializers import EmployeeSerializer
from apps.users.models import UserProfile


class EmployeePinValidationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        existing_user = user_model.objects.create_user(username="existing", password="483921", is_active=True)
        UserProfile.objects.create(user=existing_user, role="cashier", is_active=True)

    def test_create_employee_rejects_non_numeric_pin(self):
        serializer = EmployeeSerializer(
            data={
                "full_name": "Empleado Uno",
                "email": "empleado1@example.com",
                "role": "cashier",
                "status": "active",
                "create_user": True,
                "user": {
                    "username": "empleado1",
                    "email": "empleado1@example.com",
                    "password": "12ab56",
                    "role": "cashier",
                },
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("PIN", str(serializer.errors))

    def test_create_employee_rejects_duplicated_pin(self):
        serializer = EmployeeSerializer(
            data={
                "full_name": "Empleado Dos",
                "email": "empleado2@example.com",
                "role": "cashier",
                "status": "active",
                "create_user": True,
                "user": {
                    "username": "empleado2",
                    "email": "empleado2@example.com",
                    "password": "483921",
                    "role": "cashier",
                },
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaisesMessage(serializers.ValidationError, "PIN ya usado por otro usuario"):
            serializer.save()

    def test_create_employee_accepts_pin_with_leading_zero(self):
        serializer = EmployeeSerializer(
            data={
                "full_name": "Empleado Cero",
                "email": "empleado0@example.com",
                "role": "cashier",
                "status": "active",
                "create_user": True,
                "user": {
                    "username": "empleado0",
                    "password": "070302",
                    "role": "cashier",
                },
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        employee = serializer.save()
        self.assertTrue(employee.user.check_password("070302"))

    def test_create_employee_rejects_pin_not_six_digits(self):
        serializer = EmployeeSerializer(
            data={
                "full_name": "Empleado Corto",
                "email": "empleadocorto@example.com",
                "role": "cashier",
                "status": "active",
                "create_user": True,
                "user": {
                    "username": "empleadocorto",
                    "password": "12345",
                    "role": "cashier",
                },
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("PIN", str(serializer.errors))

    def test_update_employee_pin_changes_password(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(username="emp3", password="111111", is_active=True)
        UserProfile.objects.create(user=user, role="cashier", is_active=True)
        employee = Employee.objects.create(full_name="Empleado Tres", email="emp3@example.com", role="cashier", status="active", user=user)

        serializer = EmployeeSerializer(
            employee,
            data={
                "user": {
                    "username": "emp3",
                    "email": "emp3@example.com",
                    "password": "222222",
                    "role": "cashier",
                }
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        user.refresh_from_db()
        self.assertTrue(user.check_password("222222"))
        self.assertFalse(user.check_password("111111"))
