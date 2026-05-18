from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.feature_flags import get_feature_metadata
from apps.inventory.models import (
    CatalogProductInventoryLink,
    CategoryInventoryLink,
    InventoryItem,
    InventoryMovement,
    InventorySaleApplication,
    ProductInventoryOverride,
)

logger = logging.getLogger(__name__)

STOCK_POLICY_ALLOW = "allow"
STOCK_POLICY_WARN = "warn"
STOCK_POLICY_BLOCK = "block"
STOCK_POLICY_CHOICES = {STOCK_POLICY_ALLOW, STOCK_POLICY_WARN, STOCK_POLICY_BLOCK}
STOCK_POLICY_FLAG_KEY = "FF_INVENTORY_STOCK_POLICY"


class InventoryStockPolicyError(Exception):
    def __init__(self, message: str, *, availability: dict):
        super().__init__(message)
        self.message = message
        self.availability = availability


def get_inventory_stock_policy() -> str:
    metadata = get_feature_metadata(STOCK_POLICY_FLAG_KEY)
    policy = str(metadata.get("policy") or STOCK_POLICY_ALLOW).strip().lower()
    return policy if policy in STOCK_POLICY_CHOICES else STOCK_POLICY_ALLOW


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


def _order_inventory_requirements(order) -> tuple[dict[int, Decimal], dict[int, list[dict]]]:
    required: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    affected: dict[int, list[dict]] = defaultdict(list)
    for order_item in order.items.select_related("product").all():
        if not order_item.product_id or not order_item.product:
            continue
        product = order_item.product
        quantity = Decimal(order_item.quantity)
        for inventory_item_id, qty_required in resolve_effective_inventory_links_for_product(product).items():
            total = quantity * Decimal(qty_required)
            if total == 0:
                continue
            required[inventory_item_id] += total
            affected[inventory_item_id].append(
                {
                    "product_id": product.id,
                    "product_name": order_item.product_name_snapshot or product.name,
                    "quantity": str(quantity),
                }
            )
    return required, affected


def check_order_inventory_availability(order, *, policy: str | None = None) -> dict:
    policy_value = policy or get_inventory_stock_policy()
    required, affected = _order_inventory_requirements(order)
    if not required:
        return {"ok": True, "policy": policy_value, "has_insufficient_stock": False, "items": []}

    item_map = InventoryItem.objects.in_bulk(required.keys())
    insufficient = []
    for inventory_item_id, total_required in required.items():
        item = item_map.get(inventory_item_id)
        if not item:
            continue
        available = Decimal(item.current_stock)
        if available < total_required:
            insufficient.append(
                {
                    "inventory_item_id": item.id,
                    "name": item.name,
                    "sku": item.sku,
                    "unit": item.unit,
                    "available": str(available),
                    "required": str(total_required),
                    "missing": str(total_required - available),
                    "affected_products": affected.get(item.id, []),
                }
            )
    has_insufficient = bool(insufficient)
    return {
        "ok": not has_insufficient,
        "policy": policy_value,
        "has_insufficient_stock": has_insufficient,
        "items": insufficient,
        **({"message": "Hay artículos con stock insuficiente."} if has_insufficient else {}),
    }


def validate_order_inventory_policy(order, *, warning_confirmed: bool = False) -> dict:
    availability = check_order_inventory_availability(order)
    if not availability["has_insufficient_stock"]:
        return availability
    policy = availability["policy"]
    if policy == STOCK_POLICY_BLOCK:
        raise InventoryStockPolicyError("No se puede completar la venta porque hay inventario insuficiente.", availability=availability)
    if policy == STOCK_POLICY_WARN and not warning_confirmed:
        raise InventoryStockPolicyError("Hay inventario insuficiente. Confirma para continuar con la venta.", availability=availability)
    return availability


def apply_inventory_for_order(order, *, user=None, warning_confirmed: bool = False) -> bool:
    """Aplica descuento de inventario para una orden pagada. Idempotente por orden."""
    if getattr(order, "financial_status", "") != "paid":
        return False

    with transaction.atomic():
        order_locked = order.__class__.objects.select_for_update().get(pk=order.pk)
        if InventorySaleApplication.objects.filter(order=order_locked).exists():
            logger.info("inventory.sale.skip_already_applied order_id=%s", order_locked.id)
            return False

        validate_order_inventory_policy(order_locked, warning_confirmed=warning_confirmed)
        deltas, _affected = _order_inventory_requirements(order_locked)

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
        logger.info("inventory.sale.applied order_id=%s item_deltas=%s", order_locked.id, len(deltas))
        return True


def reverse_inventory_for_order(order, *, user=None, reason: str = "") -> dict:
    """Restaura inventario descontado por venta. Idempotente por orden."""
    with transaction.atomic():
        order_locked = order.__class__.objects.select_for_update().get(pk=order.pk)
        application = InventorySaleApplication.objects.select_for_update().filter(order=order_locked).first()
        if not application:
            return {"reversed": False, "movements_created": 0, "detail": "La orden no tiene descuento de inventario aplicado."}
        if application.reversed_at:
            return {"reversed": False, "movements_created": 0, "detail": "El inventario de esta orden ya fue revertido."}

        original_movements = list(
            InventoryMovement.objects.filter(
                movement_type=InventoryMovement.TYPE_SALE_DEDUCTION,
                reference_type="order",
                reference_id=str(order_locked.id),
            ).select_related("inventory_item").order_by("id")
        )
        if not original_movements:
            application.reversed_at = timezone.now()
            application.reversed_by = user
            application.reversal_reason = reason[:255]
            application.save(update_fields=["reversed_at", "reversed_by", "reversal_reason"])
            return {"reversed": False, "movements_created": 0, "detail": "No se encontraron movimientos de venta para revertir."}

        movements_created = 0
        display_reason = (reason or f"Reversión por devolución de venta #{order_locked.order_number}")[:255]
        for movement in original_movements:
            item = InventoryItem.objects.select_for_update().get(pk=movement.inventory_item_id)
            restore_qty = abs(Decimal(movement.quantity_change))
            before = Decimal(item.current_stock)
            after = before + restore_qty
            item.current_stock = after
            item.save(update_fields=["current_stock", "updated_at"])
            InventoryMovement.objects.create(
                inventory_item=item,
                movement_type=InventoryMovement.TYPE_REVERSAL,
                quantity_change=restore_qty,
                quantity_before=before,
                quantity_after=after,
                reference_type="order_reversal",
                reference_id=str(order_locked.id),
                reason=f"{display_reason} (movimiento original #{movement.id})",
                created_by=user,
            )
            movements_created += 1

        application.reversed_at = timezone.now()
        application.reversed_by = user
        application.reversal_reason = display_reason
        application.save(update_fields=["reversed_at", "reversed_by", "reversal_reason"])
        logger.info("inventory.sale.reversed order_id=%s movements_created=%s", order_locked.id, movements_created)
        return {"reversed": True, "movements_created": movements_created, "detail": "Inventario revertido correctamente."}
