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
