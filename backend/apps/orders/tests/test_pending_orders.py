from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem
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
        self.category = Category.objects.create(name="Bebidas")
        self.product = Product.objects.create(
            name="Soda",
            description="",
            price="1.00",
            category=self.category,
            available=True,
            requires_kitchen=False,
        )

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

    def test_finalized_tab_only_includes_orders_that_passed_open_orders(self):
        non_open_order = Order.objects.create(
            order_number=999,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="paid",
            subtotal="4.00",
            tax="0.00",
            total="4.00",
            is_pending=False,
            pending_completion_type="none",
            pending_reference="",
        )
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 5"
        self.order.pending_state = "pending_payment"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "updated_at"])
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False, "removal_reason": "Pagada en POS", "completion_type": "paid"},
            format="json",
        )
        res = self.client.get("/api/orders/pending/?tab=finalized")
        self.assertEqual(res.status_code, 200)
        returned_ids = [row["id"] for row in res.data["results"]]
        self.assertIn(self.order.id, returned_ids)
        self.assertNotIn(non_open_order.id, returned_ids)

    def test_resave_pending_preserves_reference_and_updates_total(self):
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 8"
        self.order.pending_state = "pending_payment"
        self.order.total = "8.74"
        self.order.subtotal = "8.74"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "total", "subtotal", "updated_at"])
        old_marked_at = self.order.pending_marked_at

        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {
                "is_pending": True,
                "pending_reference": "CAMBIO-NO-PERMITIDO",
                "items": [
                    {
                        "source_order_item_id": None,
                        "product_id": self.product.id,
                        "product_name_snapshot": "Soda",
                        "quantity": 2,
                        "price_snapshot": "6.90",
                        "modifiers": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.pending_reference, "Mesa 8")
        self.assertEqual(str(self.order.total), "13.80")
        self.assertEqual(self.order.pending_marked_at, old_marked_at)

    def test_cashier_cannot_remove_item_from_pending_without_manager_pin(self):
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 1"
        self.order.pending_state = "pending_payment"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "updated_at"])
        order_item = OrderItem.objects.create(order=self.order, product=self.product, product_name_snapshot="Soda", price_snapshot="2.00", quantity=1)
        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": True, "pending_reference": "Mesa 1", "items": []},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
        self.assertTrue(OrderItem.objects.filter(id=order_item.id).exists())

    def test_manager_pin_allows_cashier_to_remove_item_from_pending(self):
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 2"
        self.order.pending_state = "pending_payment"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "updated_at"])
        OrderItem.objects.create(order=self.order, product=self.product, product_name_snapshot="Soda", price_snapshot="2.00", quantity=1)
        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": True, "pending_reference": "Mesa 2", "authorization_pin": "222222", "items": []},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.items.count(), 0)

    def test_resave_existing_pending_updates_same_order_without_creating_new(self):
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 11"
        self.order.pending_state = "pending_payment"
        self.order.total = "8.99"
        self.order.subtotal = "8.99"
        self.order.discount_total = "1.00"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "total", "subtotal", "discount_total", "updated_at"])
        before_count = Order.objects.count()

        res = self.client.post(
            f"/api/orders/{self.order.id}/pending/",
            {
                "is_pending": True,
                "pending_reference": "Mesa 11",
                "items": [
                    {
                        "source_order_item_id": None,
                        "product_id": self.product.id,
                        "product_name_snapshot": "Soda",
                        "quantity": 3,
                        "price_snapshot": "7.49",
                        "modifiers": [],
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Order.objects.count(), before_count)
        self.order.refresh_from_db()
        self.assertEqual(self.order.id, res.data["id"])
        self.assertEqual(str(self.order.total), "22.47")
        self.assertEqual(str(self.order.discount_total), "0.00")
        self.assertEqual(self.order.pending_reference, "Mesa 11")

    def test_finalize_paid_moves_order_out_of_pending_and_into_finalized(self):
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 15"
        self.order.pending_state = "pending_payment"
        self.order.payment_status = "paid"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "payment_status", "updated_at"])
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        res = manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": False, "removal_reason": "Pagada en POS", "completion_type": "paid"},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.data)
        pending_res = self.client.get("/api/orders/pending/?tab=pending&q=Mesa 15")
        finalized_res = self.client.get("/api/orders/pending/?tab=finalized&q=Mesa 15")
        self.assertEqual(pending_res.status_code, 200)
        self.assertEqual(finalized_res.status_code, 200)
        self.assertEqual(pending_res.data["count"], 0)
        self.assertEqual(finalized_res.data["count"], 1)

    def test_cannot_remove_items_when_order_already_sent_to_kitchen(self):
        kitchen_product = Product.objects.create(
            name="Hamburguesa",
            description="",
            price="2.00",
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        self.order.is_pending = True
        self.order.pending_reference = "Mesa 3"
        self.order.pending_state = "in_kitchen"
        self.order.send_to_kitchen = True
        self.order.status = "preparing"
        self.order.save(update_fields=["is_pending", "pending_reference", "pending_state", "send_to_kitchen", "status", "updated_at"])
        OrderItem.objects.create(order=self.order, product=kitchen_product, product_name_snapshot="Hamburguesa", price_snapshot="2.00", quantity=1)
        manager_client = APIClient()
        manager_client.force_authenticate(self.manager)
        res = manager_client.post(
            f"/api/orders/{self.order.id}/pending/",
            {"is_pending": True, "pending_reference": "Mesa 3", "items": []},
            format="json",
        )
        self.assertEqual(res.status_code, 403)
