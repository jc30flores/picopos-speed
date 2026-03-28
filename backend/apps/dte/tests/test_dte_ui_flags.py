from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType, Customer
from apps.dte.models import DTERecord, CreditNote
from apps.orders.models import Order
from apps.users.models import UserProfile


class DTEUIFlagsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cash_flags", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)

        self.branch = Branch.objects.create(name="Main", code="MAIN-F")
        self.service_type = ServiceType.objects.create(key="dine-in-f", label="En local")
        self.customer = Customer.objects.create(
            name="Cliente Test",
            full_name="Cliente Test",
            correo="cliente@test.com",
            telefono="77778888",
            client_type="CCF",
            is_deleted=False,
        )

    def _record(self, *, dte_type: str, status: str, created_at=None):
        order = Order.objects.create(
            order_number=1000 + DTERecord.objects.count(),
            branch=self.branch,
            service_type=self.service_type,
            customer=self.customer,
            subtotal=Decimal("10.00"),
            tax=Decimal("0.00"),
            total=Decimal("10.00"),
        )
        rec = DTERecord.objects.create(
            order=order,
            branch=self.branch,
            dte_type=dte_type,
            status=status,
            control_number=f"DTE-{order.id}",
            codigo_generacion=f"{'A' * 35}{order.id % 10}",
            receiver_name="Cliente",
            total_amount=Decimal("10.00"),
        )
        if created_at:
            DTERecord.objects.filter(id=rec.id).update(created_at=created_at)
            rec.refresh_from_db()
        return rec

    def test_list_returns_flags_and_summary(self):
        rec = self._record(dte_type="CCF_03", status=DTERecord.STATUS_PENDING)
        self.client.force_authenticate(self.user)
        res = self.client.get("/api/dte/issued/?page=1&page_size=10")
        self.assertEqual(res.status_code, 200)
        self.assertIn("count", res.data)
        self.assertIn("total_amount_sum", res.data)
        item = next(row for row in res.data["results"] if row["id"] == rec.id)
        self.assertTrue(item["can_resend"])
        self.assertTrue(item["can_send_email"])
        self.assertTrue(item["can_send_whatsapp"])

    def test_credit_note_disabled_when_existing_note(self):
        rec = self._record(dte_type="CCF_03", status=DTERecord.STATUS_ACCEPTED)
        CreditNote.objects.create(order=rec.order, original_dte_record=rec, motivo="test", total=Decimal("10.00"))
        self.client.force_authenticate(self.user)
        res = self.client.get(f"/api/dte/issued/{rec.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["can_credit_note"])

    def test_invalidate_window_rules(self):
        ccf_old = self._record(
            dte_type="CCF_03",
            status=DTERecord.STATUS_ACCEPTED,
            created_at=timezone.now() - timedelta(hours=26),
        )
        cf_recent = self._record(
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            created_at=timezone.now() - timedelta(days=30),
        )
        cf_old = self._record(
            dte_type="CF_01",
            status=DTERecord.STATUS_ACCEPTED,
            created_at=timezone.now() - timedelta(days=100),
        )
        self.client.force_authenticate(self.user)

        ccf_detail = self.client.get(f"/api/dte/issued/{ccf_old.id}/").data
        cf_recent_detail = self.client.get(f"/api/dte/issued/{cf_recent.id}/").data
        cf_old_detail = self.client.get(f"/api/dte/issued/{cf_old.id}/").data

        self.assertFalse(ccf_detail["can_invalidate"])
        self.assertTrue(cf_recent_detail["can_invalidate"])
        self.assertFalse(cf_old_detail["can_invalidate"])
