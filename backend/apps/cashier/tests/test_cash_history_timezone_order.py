from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cashier.models import CashSession, Register
from apps.core.models import Branch
from apps.users.models import UserProfile


class CashHistoryTimezoneOrderTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="cash_history_user", password="123456")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.register = Register.objects.create(name="Caja 1", station_name="POS 1", branch=self.branch, is_active=True)

    def test_history_orders_by_real_sort_timestamp_and_returns_sort_fields(self):
        now = timezone.now()
        # Session A: opened first day, closed next day (must appear first by sort_at)
        session_a = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            opening_cash="100.00",
            status="closed",
            closed_by=self.user,
            closing_counted_cash="100.00",
        )
        CashSession.objects.filter(pk=session_a.pk).update(
            opened_at=now - timedelta(days=2),
            closed_at=now - timedelta(days=1, hours=1),
        )

        # Session B: opened later same date but closed earlier same day
        session_b = CashSession.objects.create(
            register=self.register,
            opened_by=self.user,
            opening_cash="100.00",
            status="closed",
            closed_by=self.user,
            closing_counted_cash="100.00",
        )
        CashSession.objects.filter(pk=session_b.pk).update(
            opened_at=now - timedelta(days=1, hours=2),
            closed_at=now - timedelta(days=1, hours=3),
        )

        response = self.client.get("/api/cashier/session/history/")
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertGreaterEqual(len(rows), 2)

        ids = [row["id"] for row in rows]
        self.assertLess(ids.index(session_a.id), ids.index(session_b.id))

        for row in rows:
            self.assertIn("sort_at", row)
            self.assertIn("opened_at_ts", row)
            self.assertIn("closed_at_ts", row)
            self.assertIn("sort_at_ts", row)
