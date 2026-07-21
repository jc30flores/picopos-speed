from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, FeatureFlag, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import DiningArea, Order, OrderItem, RestaurantTable, TableSession, TableSessionTable
from apps.users.models import UserProfile


class KitchenCompleteTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.kitchen_user = user_model.objects.create_user(username="kitchen_complete", password="111111")
        self.waiter = user_model.objects.create_user(username="waiter_kitchen_complete", password="111111")
        UserProfile.objects.create(user=self.kitchen_user, role="kitchen", is_active=True)
        UserProfile.objects.create(user=self.waiter, role="waiter", is_active=True)
        FeatureFlag.objects.create(key="table_map_enabled", label="Mapa de mesas", is_enabled=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.category = Category.objects.create(name="Cocina")
        self.product = Product.objects.create(
            name="Panini Beef Melt",
            description="",
            price="5.50",
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        self.order = Order.objects.create(
            order_number=600,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="unpaid",
            subtotal="5.50",
            tax="0.00",
            total="5.50",
            is_pending=True,
            pending_reference="Mesa 2",
            pending_state="in_kitchen",
            send_to_kitchen=True,
        )
        area = DiningArea.objects.create(name="Salón")
        table = RestaurantTable.objects.create(area=area, name="Mesa 2", number=2, capacity=2)
        self.session = TableSession.objects.create(
            primary_order=self.order,
            opened_by=self.waiter,
            guests_count=1,
            order_mode=TableSession.ORDER_MODE_TABLE,
            status=TableSession.STATUS_SENT_TO_KITCHEN,
        )
        TableSessionTable.objects.create(session=self.session, table=table)
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name_snapshot=self.product.name,
            price_snapshot="5.50",
            quantity=1,
            kitchen_status=OrderItem.KITCHEN_STATUS_SENT,
        )
        self.client = APIClient()

    def test_kitchen_can_complete_sent_item_and_ready_summary_updates(self):
        self.client.force_authenticate(self.kitchen_user)

        response = self.client.post(f"/api/kitchen/items/{self.item.id}/complete/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.kitchen_status, OrderItem.KITCHEN_STATUS_READY)
        self.assertIsNotNone(self.item.kitchen_ready_at)
        self.assertEqual(response.data["item"]["kitchen_status"], OrderItem.KITCHEN_STATUS_READY)

        summary = self.client.get("/api/orders/tables/ready-summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["total_ready"], 1)
        self.assertEqual(summary.data["tables"][0]["items"][0]["id"], self.item.id)

    def test_complete_is_idempotent_for_already_ready_item(self):
        self.client.force_authenticate(self.kitchen_user)
        self.item.kitchen_status = OrderItem.KITCHEN_STATUS_READY
        self.item.save(update_fields=["kitchen_status"])

        response = self.client.post(f"/api/kitchen/items/{self.item.id}/complete/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["code"], "ALREADY_READY")

    def test_waiter_cannot_complete_kitchen_item(self):
        self.client.force_authenticate(self.waiter)

        response = self.client.post(f"/api/kitchen/items/{self.item.id}/complete/", {}, format="json")

        self.assertEqual(response.status_code, 403, response.data)
        self.assertEqual(str(response.data["detail"]), "El rol Mesero solo puede visualizar cocina.")

    def test_pending_item_returns_controlled_not_in_kitchen_response(self):
        self.client.force_authenticate(self.kitchen_user)
        self.item.kitchen_status = OrderItem.KITCHEN_STATUS_PENDING
        self.item.save(update_fields=["kitchen_status"])

        response = self.client.post(f"/api/kitchen/items/{self.item.id}/complete/", {}, format="json")

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["code"], "NOT_IN_KITCHEN")

    def test_waiter_can_serve_ready_item(self):
        self.client.force_authenticate(self.waiter)
        self.item.kitchen_status = OrderItem.KITCHEN_STATUS_READY
        self.item.save(update_fields=["kitchen_status"])

        response = self.client.post(f"/api/kitchen/items/{self.item.id}/serve/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.kitchen_status, OrderItem.KITCHEN_STATUS_DELIVERED)
