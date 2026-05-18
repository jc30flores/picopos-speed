from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import FeatureFlag
from apps.inventory.models import InventoryItem, InventoryMovement, InventorySupplier, PurchaseOrder
from apps.users.models import UserProfile


class InventoryAdvancedTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="manager", password="1234")
        UserProfile.objects.create(user=self.user, role="manager", is_active=True)
        FeatureFlag.objects.update_or_create(key="FF_INVENTORY", defaults={"label": "Inventario avanzado", "description": "", "is_enabled": True})
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_supplier_item_purchase_order_and_receipt_flow(self):
        supplier_res = self.client.post("/api/inventory/suppliers/", {"name": "Proveedor Uno", "code": "P-1", "is_active": True}, format="json")
        self.assertEqual(supplier_res.status_code, 201)
        supplier_id = supplier_res.data["id"]

        item = InventoryItem.objects.create(name="Coca Cola", sku="COCA", unit="unidad", current_stock=Decimal("0"), supplier_id=supplier_id, unit_cost=Decimal("0.50"), purchase_unit="Caja", purchase_to_inventory_factor=Decimal("24"))
        order_res = self.client.post("/api/inventory/purchase-orders/", {
            "supplier": supplier_id,
            "payment_category": "cash",
            "lines": [{"inventory_item": item.id, "quantity_ordered": "2", "purchase_unit": "Caja", "purchase_to_inventory_factor": "24", "unit_cost": "12.00"}],
        }, format="json")
        self.assertEqual(order_res.status_code, 201)
        order_id = order_res.data["id"]
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("0"))

        approve_res = self.client.post(f"/api/inventory/purchase-orders/{order_id}/approve/", {}, format="json")
        self.assertEqual(approve_res.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("0"))

        line_id = approve_res.data["lines"][0]["id"]
        receive_res = self.client.post(f"/api/inventory/purchase-orders/{order_id}/receive/", {"lines": [{"line_id": line_id, "quantity_received": "1"}], "update_unit_cost": True}, format="json")
        self.assertEqual(receive_res.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.current_stock, Decimal("24.000"))
        self.assertTrue(InventoryMovement.objects.filter(inventory_item=item, movement_type=InventoryMovement.TYPE_PURCHASE_RECEIPT).exists())
        self.assertEqual(receive_res.data["order"]["status"], PurchaseOrder.STATUS_PARTIALLY_RECEIVED)

    def test_advanced_flag_blocks_endpoints(self):
        FeatureFlag.objects.filter(key="FF_INVENTORY").update(is_enabled=False)
        res = self.client.get("/api/inventory/suppliers/")
        self.assertEqual(res.status_code, 403)
