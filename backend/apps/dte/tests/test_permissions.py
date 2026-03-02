from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import UserProfile


class DTEPermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)

    def test_list_requires_auth(self):
        res = self.client.get('/api/dte/issued/')
        self.assertIn(res.status_code, [403, 401])

    def test_cashier_can_list(self):
        self.client.force_authenticate(self.user)
        res = self.client.get('/api/dte/issued/')
        self.assertEqual(res.status_code, 200)
