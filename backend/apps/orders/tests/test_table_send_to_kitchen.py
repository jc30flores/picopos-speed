from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, FeatureFlag, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import DiningArea, Order, OrderItem, RestaurantTable, TableSession, TableSessionTable
from apps.users.models import UserProfile


class TableSendToKitchenTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.waiter = user_model.objects.create_user(username="waiter_table_send", password="111111")
        UserProfile.objects.create(user=self.waiter, role="waiter", is_active=True)
        FeatureFlag.objects.create(key="table_map_enabled", label="Mapa de mesas", is_enabled=True)
        self.branch = Branch.objects.create(name="Main", code="MAIN")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.category = Category.objects.create(name="Bebidas")
        self.no_kitchen_product = Product.objects.create(
            name="Coca Cola",
            description="",
            price="1.50",
            category=self.category,
            available=True,
            requires_kitchen=False,
        )
        self.kitchen_product = Product.objects.create(
            name="Panini Beef Melt",
            description="",
            price="5.50",
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        self.order = Order.objects.create(
            order_number=500,
            branch=self.branch,
            service_type=self.service_type,
            status="waiting_payment",
            payment_status="unpaid",
            subtotal="1.50",
            tax="0.00",
            total="1.50",
            is_pending=True,
            pending_reference="Mesa 1",
            pending_state="pending_payment",
        )
        area = DiningArea.objects.create(name="Salón")
        table = RestaurantTable.objects.create(area=area, name="Mesa 1", number=1, capacity=2)
        self.session = TableSession.objects.create(
            primary_order=self.order,
            opened_by=self.waiter,
            guests_count=1,
            order_mode=TableSession.ORDER_MODE_TABLE,
        )
        TableSessionTable.objects.create(session=self.session, table=table)
        self.client = APIClient()
        self.client.force_authenticate(self.waiter)

    def test_non_kitchen_product_is_saved_without_kitchen_routing(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.no_kitchen_product,
            product_name_snapshot="Coca Cola",
            price_snapshot="1.50",
            quantity=1,
            kitchen_status=OrderItem.KITCHEN_STATUS_PENDING,
        )

        response = self.client.post(
            f"/api/orders/tables/sessions/{self.session.id}/send-to-kitchen/",
            {"scope": "table"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sent_count"], 0)
        self.assertEqual(response.data["saved_count"], 1)
        item.refresh_from_db()
        self.assertEqual(item.kitchen_status, OrderItem.KITCHEN_STATUS_DELIVERED)
        self.assertIsNotNone(item.kitchen_delivered_at)
        self.order.refresh_from_db()
        self.assertFalse(self.order.send_to_kitchen)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, TableSession.STATUS_OPEN)

    def test_kitchen_product_is_sent_and_visible_in_kitchen_summary(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.kitchen_product,
            product_name_snapshot="Panini Beef Melt",
            price_snapshot="5.50",
            quantity=1,
            kitchen_status=OrderItem.KITCHEN_STATUS_PENDING,
        )

        response = self.client.post(
            f"/api/orders/tables/sessions/{self.session.id}/send-to-kitchen/",
            {"scope": "table"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sent_count"], 1)
        self.assertEqual(response.data["saved_count"], 0)
        item.refresh_from_db()
        self.assertEqual(item.kitchen_status, OrderItem.KITCHEN_STATUS_SENT)
        self.assertIsNotNone(item.kitchen_sent_at)
        self.order.refresh_from_db()
        self.assertTrue(self.order.send_to_kitchen)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, TableSession.STATUS_SENT_TO_KITCHEN)

        summary = self.client.get("/api/orders/tables/kitchen-summary/")
        self.assertEqual(summary.status_code, 200, summary.data)
        self.assertEqual(summary.data["sessions"][0]["items"][0]["id"], item.id)

    def test_mixed_products_route_only_kitchen_items(self):
        kitchen_item = OrderItem.objects.create(
            order=self.order,
            product=self.kitchen_product,
            product_name_snapshot="Panini Beef Melt",
            price_snapshot="5.50",
            quantity=1,
            kitchen_status=OrderItem.KITCHEN_STATUS_PENDING,
        )
        no_kitchen_item = OrderItem.objects.create(
            order=self.order,
            product=self.no_kitchen_product,
            product_name_snapshot="Coca Cola",
            price_snapshot="1.50",
            quantity=1,
            kitchen_status=OrderItem.KITCHEN_STATUS_PENDING,
        )

        response = self.client.post(
            f"/api/orders/tables/sessions/{self.session.id}/send-to-kitchen/",
            {"scope": "table"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sent_count"], 1)
        self.assertEqual(response.data["saved_count"], 1)
        self.assertEqual(response.data["detail"], "Pedido enviado. Algunos productos no van a cocina.")
        kitchen_item.refresh_from_db()
        no_kitchen_item.refresh_from_db()
        self.assertEqual(kitchen_item.kitchen_status, OrderItem.KITCHEN_STATUS_SENT)
        self.assertEqual(no_kitchen_item.kitchen_status, OrderItem.KITCHEN_STATUS_DELIVERED)

    def test_empty_order_returns_controlled_response(self):
        response = self.client.post(
            f"/api/orders/tables/sessions/{self.session.id}/send-to-kitchen/",
            {"scope": "table"},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data["detail"], "No hay productos pendientes para enviar.")

    def test_repeated_send_does_not_duplicate_or_resend_items(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.kitchen_product,
            product_name_snapshot="Panini Beef Melt",
            price_snapshot="5.50",
            quantity=1,
            kitchen_status=OrderItem.KITCHEN_STATUS_PENDING,
        )
        first_response = self.client.post(
            f"/api/orders/tables/sessions/{self.session.id}/send-to-kitchen/",
            {"scope": "table"},
            format="json",
        )
        second_response = self.client.post(
            f"/api/orders/tables/sessions/{self.session.id}/send-to-kitchen/",
            {"scope": "table"},
            format="json",
        )

        self.assertEqual(first_response.status_code, 200, first_response.data)
        self.assertEqual(second_response.status_code, 200, second_response.data)
        self.assertEqual(first_response.data["sent_count"], 1)
        self.assertEqual(second_response.data["sent_count"], 0)
        self.assertEqual(second_response.data["saved_count"], 0)
        self.assertEqual(OrderItem.objects.filter(order=self.order).count(), 1)
        item.refresh_from_db()
        self.assertEqual(item.kitchen_status, OrderItem.KITCHEN_STATUS_SENT)
