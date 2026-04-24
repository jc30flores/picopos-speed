from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from django.db import transaction

from apps.inventory.models import (
    CatalogProductInventoryLink,
    CategoryInventoryLink,
    InventoryItem,
    InventoryMovement,
    InventorySaleApplication,
    ProductInventoryOverride,
)

logger = logging.getLogger(__name__)


def resolve_effective_inventory_links_for_product(product) -> dict[int, Decimal]:
    effective: dict[int, Decimal] = {}
    category_links = CategoryInventoryLink.objects.filter(category_id=product.category_id).select_related("inventory_item")
    category_by_id = {}
    for row in category_links:
        effective[row.inventory_item_id] = Decimal(row.quantity_required)
        category_by_id[row.id] = row

    overrides = ProductInventoryOverride.objects.filter(product_id=product.id, category_link_id__in=category_by_id.keys())
    for override in overrides:
        link = category_by_id.get(override.category_link_id)
        if not link:
            continue
        if override.is_disabled:
            effective.pop(link.inventory_item_id, None)
        elif override.quantity_required is not None:
            effective[link.inventory_item_id] = Decimal(override.quantity_required)

    direct_links = CatalogProductInventoryLink.objects.filter(catalog_product_id=product.id).select_related("inventory_item")
    for direct in direct_links:
        # Direct link has precedence to avoid duplicate deductions.
        effective[direct.inventory_item_id] = Decimal(direct.quantity_required)
    return effective


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
            product = order_item.product
            if not product:
                continue
            effective_links = resolve_effective_inventory_links_for_product(product)
            for inventory_item_id, qty_required in effective_links.items():
                deltas[inventory_item_id] += Decimal(order_item.quantity) * Decimal(qty_required)

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
