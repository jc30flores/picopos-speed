from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal, ROUND_FLOOR

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
STOCK_POLICY_INHERIT = "inherit"
STOCK_POLICY_CHOICES = {STOCK_POLICY_ALLOW, STOCK_POLICY_WARN, STOCK_POLICY_BLOCK}
PRODUCT_STOCK_POLICY_CHOICES = {STOCK_POLICY_INHERIT, STOCK_POLICY_ALLOW, STOCK_POLICY_WARN, STOCK_POLICY_BLOCK}
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


def resolve_inventory_policy_for_product(product) -> str:
    raw_policy = str(getattr(product, "inventory_stock_policy", STOCK_POLICY_INHERIT) or STOCK_POLICY_INHERIT).strip().lower()
    if raw_policy == STOCK_POLICY_INHERIT or raw_policy not in PRODUCT_STOCK_POLICY_CHOICES:
        return get_inventory_stock_policy()
    return raw_policy


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


def _product_policy_action(policies: set[str]) -> str:
    if STOCK_POLICY_BLOCK in policies:
        return STOCK_POLICY_BLOCK
    if STOCK_POLICY_WARN in policies:
        return STOCK_POLICY_WARN
    return STOCK_POLICY_ALLOW


def _order_inventory_requirements(order) -> tuple[dict[int, Decimal], dict[int, list[dict]]]:
    required: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    affected: dict[int, list[dict]] = defaultdict(list)
    for order_item in order.items.select_related("product").all():
        if not order_item.product_id or not order_item.product:
            continue
        product = order_item.product
        quantity = Decimal(order_item.quantity)
        resolved_policy = resolve_inventory_policy_for_product(product)
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
                    "required": str(total),
                    "resolved_policy": resolved_policy,
                    "action": resolved_policy,
                }
            )
    return required, affected


def check_order_inventory_availability(order, *, policy: str | None = None) -> dict:
    required, affected = _order_inventory_requirements(order)
    default_policy = policy or get_inventory_stock_policy()
    if not required:
        return {"ok": True, "policy": default_policy, "has_insufficient_stock": False, "items": []}

    item_map = InventoryItem.objects.in_bulk(required.keys())
    insufficient = []
    blocking = False
    warning = False
    for inventory_item_id, total_required in required.items():
        item = item_map.get(inventory_item_id)
        if not item:
            continue
        available = Decimal(item.current_stock)
        if available < total_required:
            affected_products = affected.get(item.id, [])
            action = _product_policy_action({row.get("resolved_policy", default_policy) for row in affected_products})
            blocking = blocking or action == STOCK_POLICY_BLOCK
            warning = warning or action == STOCK_POLICY_WARN
            insufficient.append(
                {
                    "inventory_item_id": item.id,
                    "name": item.name,
                    "sku": item.sku,
                    "unit": item.unit,
                    "available": str(available),
                    "required": str(total_required),
                    "missing": str(total_required - available),
                    "action": action,
                    "affected_products": affected_products,
                }
            )
    has_insufficient = bool(insufficient)
    effective_policy = STOCK_POLICY_BLOCK if blocking else STOCK_POLICY_WARN if warning else default_policy
    return {
        "ok": not has_insufficient or (not blocking and not warning),
        "policy": effective_policy,
        "has_insufficient_stock": has_insufficient,
        "has_blocking_stock": blocking,
        "has_warning_stock": warning,
        "items": insufficient,
        **({"message": "Hay artículos con stock insuficiente."} if has_insufficient else {}),
    }


def validate_order_inventory_policy(order, *, warning_confirmed: bool = False) -> dict:
    availability = check_order_inventory_availability(order)
    if not availability["has_insufficient_stock"]:
        return availability
    if availability.get("has_blocking_stock"):
        raise InventoryStockPolicyError("No se puede completar la venta porque hay inventario insuficiente.", availability=availability)
    if availability.get("has_warning_stock") and not warning_confirmed:
        raise InventoryStockPolicyError("Hay inventario insuficiente. Confirma para continuar con la venta.", availability=availability)
    return availability


def _cart_rows(cart_items: list[dict]) -> dict[int, Decimal]:
    rows: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in cart_items or []:
        try:
            product_id = int(row.get("product_id") or row.get("productId"))
            quantity = Decimal(str(row.get("quantity") or 0))
        except Exception:
            continue
        if product_id > 0 and quantity > 0:
            rows[product_id] += quantity
    return rows


def check_cart_inventory_availability(*, cart_items: list[dict], candidate_product_ids: list[int] | None = None) -> dict:
    from apps.menu.models import Product

    cart_by_product = _cart_rows(cart_items)
    candidate_ids = {int(pid) for pid in (candidate_product_ids or []) if str(pid).isdigit()}
    product_ids = set(cart_by_product.keys()) | candidate_ids
    products = Product.objects.filter(id__in=product_ids).select_related("category")
    product_map = {product.id: product for product in products}

    links_by_product: dict[int, dict[int, Decimal]] = {}
    reserved_by_item: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    inventory_item_ids: set[int] = set()
    for product_id, quantity in cart_by_product.items():
        product = product_map.get(product_id)
        if not product:
            continue
        links = resolve_effective_inventory_links_for_product(product)
        links_by_product[product_id] = links
        for item_id, qty_required in links.items():
            reserved_by_item[item_id] += quantity * Decimal(qty_required)
            inventory_item_ids.add(item_id)
    for product_id in candidate_ids:
        product = product_map.get(product_id)
        if product and product_id not in links_by_product:
            links = resolve_effective_inventory_links_for_product(product)
            links_by_product[product_id] = links
            inventory_item_ids.update(links.keys())

    item_map = InventoryItem.objects.in_bulk(inventory_item_ids)
    rows = []
    cart_has_blocked_items = False
    cart_has_warnings = False
    for product_id in sorted(product_ids):
        product = product_map.get(product_id)
        if not product:
            continue
        links = links_by_product.get(product_id) or resolve_effective_inventory_links_for_product(product)
        current_qty = cart_by_product.get(product_id, Decimal("0"))
        resolved_policy = resolve_inventory_policy_for_product(product)
        is_tracked = bool(links)
        max_addable: int | None = None
        missing = []
        if is_tracked:
            for item_id, qty_required in links.items():
                if qty_required <= 0:
                    continue
                item = item_map.get(item_id)
                if not item:
                    continue
                available = Decimal(item.current_stock)
                reserved_total = reserved_by_item.get(item_id, Decimal("0"))
                reserved_others = reserved_total - (current_qty * Decimal(qty_required))
                remaining_for_product = available - reserved_others - (current_qty * Decimal(qty_required))
                addable_for_item = max(int((remaining_for_product / Decimal(qty_required)).to_integral_value(rounding=ROUND_FLOOR)), 0)
                max_addable = addable_for_item if max_addable is None else min(max_addable, addable_for_item)
                if remaining_for_product < Decimal(qty_required):
                    missing.append(
                        {
                            "inventory_item_id": item.id,
                            "name": item.name,
                            "available": str(available),
                            "reserved_in_cart": str(reserved_total),
                            "required_for_next": str(qty_required),
                            "missing": str(Decimal(qty_required) - remaining_for_product),
                            "unit": item.unit,
                        }
                    )
        if max_addable is None:
            max_addable = 999999
        can_add_one = (not is_tracked) or max_addable > 0 or resolved_policy != STOCK_POLICY_BLOCK
        status = "ok"
        message = ""
        if is_tracked and max_addable <= 0:
            if resolved_policy == STOCK_POLICY_BLOCK:
                status = "blocked"
                message = "No hay stock suficiente para agregar más unidades."
                cart_has_blocked_items = cart_has_blocked_items or current_qty > 0
            elif resolved_policy == STOCK_POLICY_WARN:
                status = "warning"
                message = "Este producto no tiene stock suficiente."
                cart_has_warnings = True
            else:
                status = "allowed_without_stock"
                message = "Venta permitida sin stock."
        rows.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "resolved_policy": resolved_policy,
                "is_tracked": is_tracked,
                "can_add_one": can_add_one,
                "max_addable_now": max_addable,
                "current_cart_quantity": str(current_qty),
                "status": status,
                "message": message,
                "missing": missing,
            }
        )
    return {"items": rows, "cart_has_blocked_items": cart_has_blocked_items, "cart_has_warnings": cart_has_warnings}


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
