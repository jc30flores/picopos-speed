from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.serializers import OrderCreateSerializer
from apps.orders.services.snapshots import persist_sale_snapshot


class OrderCustomItemSnapshotTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Sucursal Centro", code="CENTRO2")
        self.service_type = ServiceType.objects.create(key="para-llevar", label="Para llevar")
        self.category = Category.objects.create(name="BEBIDAS")
        self.product = Product.objects.create(name="Soda", description="", price=Decimal("1.50"), category=self.category, available=True)

    def test_create_order_with_manual_item_persists_snapshot_fields(self):
        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "channel": "pos",
                "items": [
                    {
                        "is_custom": True,
                        "custom_name": "Propina solidaria",
                        "unit_price": "2.25",
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
