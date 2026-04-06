from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.exceptions import PermissionDenied

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.serializers import OrderCreateSerializer
from apps.orders.services.snapshots import persist_sale_snapshot
from apps.users.models import UserProfile


class OrderCustomItemSnapshotTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Sucursal Centro", code="CENTRO2")
        self.service_type = ServiceType.objects.create(key="para-llevar", label="Para llevar")
        self.category = Category.objects.create(name="BEBIDAS")
        self.product = Product.objects.create(name="Soda", description="", price=Decimal("1.50"), category=self.category, available=True)
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user(username="admin_price_override", password="246810", is_active=True)
        UserProfile.objects.create(user=self.admin_user, role="admin", is_active=True)

    def test_create_order_with_manual_item_persists_snapshot_fields(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "items": [
                    {
                        "type": "MANUAL",
                        "manual_name": "Propina solidaria",
                        "manual_unit_price": "2.25",
                        "custom_code": "MANUAL-XYZ",
                        "quantity": 2,
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        item = order.items.first()
        self.assertIsNone(item.product_id)
        self.assertTrue(item.is_custom)
        self.assertEqual(item.product_name_snapshot, "Propina solidaria")
        self.assertEqual(item.price_snapshot, Decimal("2.25"))
        self.assertEqual(item.snapshot_sku_or_code, "MANUAL-XYZ")

        invoice = persist_sale_snapshot(order)
        snap_item = invoice.sale_snapshot["items"][0]
        self.assertEqual(snap_item["name"], "Propina solidaria")
        self.assertEqual(snap_item["unit_price"], "2.25")
        self.assertTrue(snap_item["is_custom"])

    def test_create_order_with_manual_item_accepts_is_custom_in_payload(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "items": [
                    {
                        "is_custom": True,
                        "manual_name": "Recargo caja",
                        "manual_unit_price": "1.00",
                        "quantity": 1,
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        item = order.items.first()
        self.assertTrue(item.is_custom)
        self.assertIsNone(item.product_id)
        self.assertEqual(item.product_name_snapshot, "Recargo caja")
        self.assertEqual(item.price_snapshot, Decimal("1.00"))

    def test_menu_item_snapshot_keeps_original_price_after_menu_change(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "items": [
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()

        self.product.price = Decimal("3.75")
        self.product.save(update_fields=["price"])

        invoice = persist_sale_snapshot(order)
        snap_item = invoice.sale_snapshot["items"][0]
        self.assertEqual(snap_item["unit_price"], "1.50")
        self.assertEqual(snap_item["name"], "Soda")

    def test_create_order_with_menu_item_still_works(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "items": [{"product_id": self.product.id, "quantity": 2}],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        item = order.items.first()
        self.assertEqual(item.product_id, self.product.id)
        self.assertEqual(item.price_snapshot, Decimal("1.50"))
        self.assertEqual(item.quantity, 2)

    def test_order_rejects_override_without_pin(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "items": [
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "unit_price_override": "2.00",
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaisesMessage(PermissionDenied, "Código inválido"):
            serializer.save()

    def test_order_accepts_override_with_pin(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "price_change_pin": "246810",
                "items": [
                    {
                        "product_id": self.product.id,
                        "quantity": 1,
                        "unit_price_override": "2.00",
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        item = order.items.first()
        self.assertEqual(item.unit_price_override, Decimal("2.00"))


class ValidatePricePinEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="cashier_pin", password="pw")
        UserProfile.objects.create(user=self.user, role="cashier", is_active=True)
        self.client.force_authenticate(self.user)

    def test_validate_price_pin_rejects_invalid_pin(self):
        response = self.client.post("/api/orders/validate-price-pin/", {"pin": "000000"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_validate_price_pin_accepts_valid_pin(self):
        admin = get_user_model().objects.create_user(username="manager_pin_validate", password="135790")
        UserProfile.objects.create(user=admin, role="manager", is_active=True)
        response = self.client.post("/api/orders/validate-price-pin/", {"pin": "135790"}, format="json")
        self.assertEqual(response.status_code, 204)
