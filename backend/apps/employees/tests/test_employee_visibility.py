from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from apps.employees.models import Employee
from apps.users.models import UserProfile


class EmployeeVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin = get_user_model().objects.create_user(username="admin_vis", password="pw")
        UserProfile.objects.create(user=admin, role="admin", is_active=True)
        self.client.force_authenticate(admin)

    def test_list_excludes_deleted_anonymized(self):
        Employee.objects.create(full_name="Visible", role="cashier", status="active")
        Employee.objects.create(full_name="Empleado eliminado #2", role="cashier", status="inactive", is_deleted=True)
        resp = self.client.get('/api/employees/')
        self.assertEqual(resp.status_code, 200)
        names = [r['full_name'] for r in resp.data]
        self.assertIn('Visible', names)
        self.assertFalse(any(n.startswith('Empleado eliminado') for n in names))
