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
            {"is_pending": True, "pending_state": "pending_payment"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_pending)
        self.assertEqual(self.order.pending_state, "pending_payment")

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
        self.order.save(update_fields=["is_pending", "pending_state", "updated_at"])
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        res = manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_pending)

    def test_pending_list_returns_only_pending(self):
        self.order.is_pending = True
        self.order.pending_state = "pending_payment"
        self.order.save(update_fields=["is_pending", "pending_state", "updated_at"])
        res = self.client.get("/api/orders/pending/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 1)
