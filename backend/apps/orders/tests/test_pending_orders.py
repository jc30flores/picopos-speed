from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.orders.models import Order
from apps.users.models import UserProfile


class PendingOrdersTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.cashier = user_model.objects.create_user(username="cash_pending", password="111111")
        self.manager = user_model.objects.create_user(username="manager_pending", password="222222")
        UserProfile.objects.create(user=self.cashier, role="cashier", is_active=True)
        UserProfile.objects.create(user=self.manager, role="manager", is_active=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.order = Order.objects.create(
            order_number=123,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="unpaid",
            subtotal="10.00",
            tax="0.00",
            total="10.00",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)

    def test_cashier_can_mark_order_as_pending(self):
        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": True, "pending_state": "pending_payment", "pending_reference": "Mesa 4"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_pending)
        self.assertEqual(self.order.pending_state, "pending_payment")
        self.assertEqual(self.order.pending_reference, "Mesa 4")

    def test_pending_mark_requires_reference(self):
        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": True, "pending_state": "pending_payment"},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_cashier_cannot_remove_pending_without_manager_pin(self):
        self.order.is_pending = True
        self.order.pending_state = "pending_payment"
        self.order.save(update_fields=["is_pending", "pending_state", "updated_at"])
        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False},
            format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_manager_can_remove_pending_without_pin(self):
        self.order.is_pending = True
        self.order.pending_state = "pending_payment"
        self.order.pending_reference = "ORD-123"
        self.order.save(update_fields=["is_pending", "pending_state", "pending_reference", "updated_at"])
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        res = manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False, "removal_reason": "Cobrado en caja"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_pending)
        self.assertEqual(self.order.pending_completion_type, "removed")
        self.assertTrue(self.order.pending_completed_at is not None)

    def test_remove_pending_requires_reason(self):
        self.order.is_pending = True
        self.order.pending_state = "pending_payment"
        self.order.pending_reference = "ORD-999"
        self.order.save(update_fields=["is_pending", "pending_state", "pending_reference", "updated_at"])
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        res = manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False},
            format="json",
        )
        self.assertEqual(res.status_code, 400)

    def test_pending_list_returns_only_pending(self):
        self.order.is_pending = True
        self.order.pending_state = "pending_payment"
        self.order.save(update_fields=["is_pending", "pending_state", "updated_at"])
        res = self.client.get("/api/orders/pending/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)

    def test_pending_list_respects_branch_filter(self):
        other_branch = Branch.objects.create(name="Other", code="OTHER")
        other_order = Order.objects.create(
            order_number=124,
            branch=other_branch,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="unpaid",
            subtotal="8.00",
            tax="0.00",
            total="8.00",
            is_pending=True,
            pending_state="pending_payment",
            pending_reference="APP-01",
        )
        self.order.is_pending = True
        self.order.pending_state = "pending_payment"
        self.order.pending_reference = "APP-02"
        self.order.save(update_fields=["is_pending", "pending_state", "pending_reference", "updated_at"])

        res_main = self.client.get(f"/api/orders/pending/?branch_id={self.branch.id}")
        self.assertEqual(res_main.status_code, 200)
        self.assertEqual(res_main.data["count"], 1)
        self.assertEqual(res_main.data["results"][0]["id"], self.order.id)

        res_other = self.client.get(f"/api/orders/pending/?branch_id={other_branch.id}")
        self.assertEqual(res_other.status_code, 200)
        self.assertEqual(res_other.data["count"], 1)
        self.assertEqual(res_other.data["results"][0]["id"], other_order.id)

    def test_pending_list_filters_by_tab_and_reference_query(self):
        self.order.is_pending = True
        self.order.pending_state = "paid_pending_delivery"
        self.order.payment_status = "paid"
        self.order.pending_reference = "DELIV-777"
        self.order.save(update_fields=["is_pending", "pending_state", "payment_status", "pending_reference", "updated_at"])

        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False, "removal_reason": "Pagada en POS", "completion_type": "paid"},
            format="json",
        )

        res_finalized = self.client.get("/api/orders/pending/?tab=finalized&q=777")
        self.assertEqual(res_finalized.status_code, 200)
        self.assertEqual(res_finalized.data["count"], 1)

        res_pending = self.client.get("/api/orders/pending/?tab=pending&q=777")
        self.assertEqual(res_pending.status_code, 200)
        self.assertEqual(res_pending.data["count"], 0)
