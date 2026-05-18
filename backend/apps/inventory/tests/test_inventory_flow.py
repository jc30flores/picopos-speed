from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.inventory.models import (
    CatalogProductInventoryLink,
    InventoryCountLine,
    InventoryCountSession,
    InventoryItem,
    InventoryMovement,
    InventorySaleApplication,
)
from apps.inventory.services import apply_inventory_for_order
from apps.users.models import UserProfile


class InventoryFlowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="admin", password="1234")
        UserProfile.objects.create(user=self.user, role="admin", is_active=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.branch = Branch.objects.create(name="Main", code="M1")
        self.service_type = ServiceType.objects.create(key="to_go", label="To Go", is_active=True)
        self.category = Category.objects.create(name="COMIDA")
        self.product = Product.objects.create(name="Hamburguesa", description="", price=Decimal("5"), category=self.category)

    def test_inventory_item_create_add_adjust(self):
        res = self.client.post("/api/inventory/items/", {
            "name": "Pan", "sku": "PAN-1", "unit": "unidad", "initial_stock": "10", "is_active": True,
        }, format="json")
        self.assertEqual(res.status_code, 201)
        item_id = res.data["id"]

        add_res = self.client.post(f"/api/inventory/items/{item_id}/add-stock/", {"quantity": "5"}, format="json")
        self.assertEqual(add_res.status_code, 200)
        self.assertEqual(Decimal(str(add_res.data["current_stock"])), Decimal("15"))

        adjust_res = self.client.post(f"/api/inventory/items/{item_id}/adjust-stock/", {"set_stock": "12"}, format="json")
        self.assertEqual(adjust_res.status_code, 200)
        self.assertEqual(Decimal(str(adjust_res.data["current_stock"])), Decimal("12"))

    def test_sale_deduction_is_idempotent(self):
        item = InventoryItem.objects.create(name="Pan", unit="unidad", current_stock=Decimal("20"))
        CatalogProductInventoryLink.objects.create(catalog_product=self.product, inventory_item=item, quantity_required=Decimal("2"))

        order = Order.objects.create(order_number=1, branch=self.branch, service_type=self.service_type, total=Decimal("10"), amount_due_cents=1000, financial_status="paid")
        OrderItem.objects.create(order=order, product=self.product, product_name_snapshot=self.product.name, price_snapshot=Decimal("5"), quantity=2)

        applied_first = apply_inventory_for_order(order, user=self.user)
        applied_second = apply_inventory_for_order(order, user=self.user)

        item.refresh_from_db()
        self.assertTrue(applied_first)
        self.assertFalse(applied_second)
        self.assertEqual(item.current_stock, Decimal("16"))
        self.assertTrue(InventorySaleApplication.objects.filter(order=order).exists())

    def test_delete_draft_inventory_count_removes_session(self):
        item = InventoryItem.objects.create(name="Pan", unit="unidad", current_stock=Decimal("20"))
        create_res = self.client.post("/api/inventory/counts/", {"count_type": "manual", "item_ids": [item.id]}, format="json")
        self.assertEqual(create_res.status_code, 201)
        session_id = create_res.data["id"]

        delete_res = self.client.delete(f"/api/inventory/counts/{session_id}/")

        self.assertEqual(delete_res.status_code, 204)
        self.assertFalse(InventoryCountSession.objects.filter(id=session_id).exists())
        self.assertFalse(InventoryCountLine.objects.filter(session_id=session_id).exists())

    def test_delete_applied_inventory_count_is_blocked(self):
        item = InventoryItem.objects.create(name="Pan", unit="unidad", current_stock=Decimal("20"))
        session = InventoryCountSession.objects.create(count_type=InventoryCountSession.TYPE_MANUAL, status=InventoryCountSession.STATUS_APPLIED, created_by=self.user)
        InventoryCountLine.objects.create(session=session, inventory_item=item, system_stock=Decimal("20"), counted_stock=Decimal("18"))
        InventoryMovement.objects.create(inventory_item=item, movement_type=InventoryMovement.TYPE_INVENTORY_COUNT_ADJUSTMENT, quantity_change=Decimal("-2"), quantity_before=Decimal("20"), quantity_after=Decimal("18"), reference_type="inventory_count", reference_id=str(session.id), created_by=self.user)

        delete_res = self.client.delete(f"/api/inventory/counts/{session.id}/")

        self.assertEqual(delete_res.status_code, 400)
        self.assertTrue(InventoryCountSession.objects.filter(id=session.id).exists())
