from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.inventory.models import (
    CatalogProductInventoryLink,
    InventoryItem,
    InventoryMovement,
    InventorySaleApplication,
)

logger = logging.getLogger(__name__)


def apply_inventory_for_order(order, *, user=None) -> bool:
    """Aplica descuento de inventario para una orden pagada. Idempotente por orden."""
    if getattr(order, "financial_status", "") != "paid":
        return False

    with transaction.atomic():
        order_locked = order.__class__.objects.select_for_update().get(pk=order.pk)
        if InventorySaleApplication.objects.filter(order=order_locked).exists():
            logger.info("inventory.sale.skip_already_applied order_id=%s", order_locked.id)
            return False

        deltas: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        item_rows = order_locked.items.select_related("product").all()
        for order_item in item_rows:
            if not order_item.product_id:
                continue
            links = CatalogProductInventoryLink.objects.filter(catalog_product_id=order_item.product_id).select_related("inventory_item")
            for link in links:
                deltas[link.inventory_item_id] += Decimal(order_item.quantity) * Decimal(link.quantity_required)

        for inventory_item_id, total_deduction in deltas.items():
            if total_deduction == 0:
                continue
            item = InventoryItem.objects.select_for_update().get(pk=inventory_item_id)
            before = Decimal(item.current_stock)
            after = before - total_deduction
            item.current_stock = after
            item.save(update_fields=["current_stock", "updated_at"])
            InventoryMovement.objects.create(
                inventory_item=item,
                movement_type=InventoryMovement.TYPE_SALE_DEDUCTION,
                quantity_change=-total_deduction,
                quantity_before=before,
                quantity_after=after,
                reference_type="order",
                reference_id=str(order_locked.id),
                reason=f"Descuento por venta #{order_locked.order_number}",
                created_by=user,
            )

        InventorySaleApplication.objects.create(order=order_locked, applied_by=user)
        logger.info("inventory.sale.applied order_id=%s product_lines=%s item_deltas=%s", order_locked.id, item_rows.count(), len(deltas))
        return True
