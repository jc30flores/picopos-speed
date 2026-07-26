from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Iterable

from django.db.models import Sum

from apps.core.models import TaxConfig
from apps.core.money import from_cents, q2, to_cents
from apps.menu.models import Discount
from apps.orders.discount_engine import apply_discounts, discount_conditions_met, discount_has_conditions
from apps.orders.models import AppliedDiscount, Order, OrderFee, OrderItem, TableGuest, TableSession


@dataclass(frozen=True)
class ItemTotal:
    item_id: int
    table_guest_id: int | None
    guest_number: int | None
    guest_label: str
    gross_cents: int
    discount_cents: int
    net_cents: int


@dataclass(frozen=True)
class OrderTotals:
    subtotal_cents: int
    discount_cents: int
    subtotal_after_discounts_cents: int
    disposable_cents: int
    tax_cents: int
    total_cents: int
    paid_cents: int
    amount_due_cents: int
    iva_exempt_discount_cents: int
    item_totals: tuple[ItemTotal, ...]

    @property
    def subtotal(self) -> Decimal:
        return from_cents(self.subtotal_cents)

    @property
    def discount_total(self) -> Decimal:
        return from_cents(self.discount_cents)

    @property
    def subtotal_after_discounts(self) -> Decimal:
        return from_cents(self.subtotal_after_discounts_cents)

    @property
    def disposable_total(self) -> Decimal:
        return from_cents(self.disposable_cents)

    @property
    def tax_total(self) -> Decimal:
        return from_cents(self.tax_cents)

    @property
    def total(self) -> Decimal:
        return from_cents(self.total_cents)

    @property
    def paid_total(self) -> Decimal:
        return from_cents(self.paid_cents)

    @property
    def amount_due(self) -> Decimal:
        return from_cents(self.amount_due_cents)

    @property
    def iva_exempt_discount(self) -> Decimal:
        return from_cents(self.iva_exempt_discount_cents)


def _money(value: Decimal | int | str | None) -> Decimal:
    return q2(Decimal(str(value if value is not None else "0")))


def allocate_cents(total_cents: int, weights: Iterable[int]) -> list[int]:
    weights_list = [max(int(weight or 0), 0) for weight in weights]
    safe_total = max(int(total_cents or 0), 0)
    weight_total = sum(weights_list)
    if safe_total <= 0 or weight_total <= 0:
        return [0 for _ in weights_list]

    allocations: list[dict[str, int | Decimal]] = []
    allocated = 0
    for index, weight in enumerate(weights_list):
        raw = (Decimal(safe_total) * Decimal(weight)) / Decimal(weight_total)
        cents = int(raw.to_integral_value(rounding=ROUND_FLOOR))
        allocated += cents
        allocations.append({"index": index, "cents": cents, "remainder": raw - Decimal(cents)})

    remainder = safe_total - allocated
    for row in sorted(allocations, key=lambda item: (-item["remainder"], item["index"]))[:remainder]:
        row["cents"] = int(row["cents"]) + 1
    return [int(row["cents"]) for row in sorted(allocations, key=lambda item: item["index"])]


def split_cents_evenly(total_cents: int, count: int) -> list[int]:
    safe_count = max(2, min(20, int(count or 2)))
    safe_total = max(int(total_cents or 0), 0)
    base = safe_total // safe_count
    remainder = safe_total % safe_count
    return [base + (1 if index >= safe_count - remainder and remainder > 0 else 0) for index in range(safe_count)]


def _modifier_total(item: OrderItem) -> Decimal:
    return sum((Decimal(mod.modifier_price_snapshot or 0) for mod in item.applied_modifiers.all()), Decimal("0.00"))


def _item_gross_cents(item: OrderItem) -> int:
    unit = _money(item.effective_unit_price) + _money(_modifier_total(item))
    return to_cents(unit * Decimal(item.quantity or 0))


def _guest_label(item: OrderItem) -> str:
    if item.table_guest_id and item.table_guest:
        return item.table_guest.display_label
    return (item.assigned_name or "").strip() or "Mesa completa"


def _guest_number(item: OrderItem) -> int | None:
    if item.table_guest_id and item.table_guest:
        return item.table_guest.seat_number
    return None


def _active_tax_config() -> TaxConfig | None:
    return TaxConfig.objects.filter(is_active=True).order_by("-id").first()


def _tax_adjusted_totals(*, taxable_base_cents: int, order: Order) -> tuple[int, int, int]:
    tax_config = _active_tax_config()
    rate = Decimal(tax_config.rate if tax_config else Decimal("0.13"))
    tax_included = True if tax_config is None else bool(tax_config.tax_included)
    base = from_cents(taxable_base_cents)

    if bool(order.iva_exempt):
        if tax_included:
            divisor = Decimal("1.00") + rate
            exempt_discount = _money(base - (base / divisor))
            total = max(base - exempt_discount, Decimal("0.00"))
            return 0, to_cents(total), to_cents(exempt_discount)
        return 0, taxable_base_cents, 0

    if tax_included:
        divisor = Decimal("1.00") + rate
        tax = _money(base - (base / divisor))
        return to_cents(tax), taxable_base_cents, 0

    tax = _money(base * rate)
    return to_cents(tax), taxable_base_cents + to_cents(tax), 0


def _paid_cents(order: Order) -> int:
    from apps.payments.models import Payment, Refund

    paid = Payment.objects.filter(order=order).aggregate(total=Sum("amount_applied"))["total"] or Decimal("0.00")
    refunded = Refund.objects.filter(order=order).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    return max(to_cents(paid) - to_cents(refunded), 0)


def _historical_discount_cents(order: Order, gross_cents: int, explicit_item_discount_cents: int) -> int:
    if explicit_item_discount_cents > 0:
        return min(explicit_item_discount_cents, gross_cents)
    applied_total = order.applied_discounts.aggregate(total=Sum("amount_discounted"))["total"]
    if applied_total is not None:
        return min(to_cents(applied_total), gross_cents)
    return min(max(to_cents(order.discount_total) - to_cents(order.iva_exempt_discount), 0), gross_cents)


def calculate_order_item_totals(items: Iterable[OrderItem], *, fallback_discount_cents: int = 0) -> tuple[ItemTotal, ...]:
    item_list = list(items)
    gross_cents_by_item = [_item_gross_cents(item) for item in item_list]
    explicit_discount_cents_by_item = [min(to_cents(item.discount_amount), gross) for item, gross in zip(item_list, gross_cents_by_item)]
    explicit_total = sum(explicit_discount_cents_by_item)

    if explicit_total > 0 or fallback_discount_cents <= 0:
        discount_cents_by_item = explicit_discount_cents_by_item
    else:
        discount_cents_by_item = allocate_cents(min(fallback_discount_cents, sum(gross_cents_by_item)), gross_cents_by_item)

    totals = []
    for item, gross_cents, discount_cents in zip(item_list, gross_cents_by_item, discount_cents_by_item):
        discount_cents = min(max(discount_cents, 0), gross_cents)
        totals.append(
            ItemTotal(
                item_id=item.id,
                table_guest_id=item.table_guest_id,
                guest_number=_guest_number(item),
                guest_label=_guest_label(item),
                gross_cents=gross_cents,
                discount_cents=discount_cents,
                net_cents=max(gross_cents - discount_cents, 0),
            )
        )
    return tuple(totals)


def calculate_order_totals(order: Order, *, respect_locked: bool = True) -> OrderTotals:
    items = list(order.items.select_related("table_guest").prefetch_related("applied_modifiers").order_by("id"))
    if not items:
        model_total_cents = to_cents(order.total)
        payable_cents = order.amount_due_cents if order.amount_due_cents > 0 else model_total_cents
        paid_cents = _paid_cents(order)
        return OrderTotals(
            subtotal_cents=to_cents(order.subtotal or order.total),
            discount_cents=to_cents(order.discount_total),
            subtotal_after_discounts_cents=max(to_cents(order.subtotal or order.total) - to_cents(order.discount_total), 0),
            disposable_cents=to_cents(order.disposable_total),
            tax_cents=to_cents(order.tax),
            total_cents=payable_cents if respect_locked and order.financial_locked_at and payable_cents > 0 else model_total_cents,
            paid_cents=paid_cents,
            amount_due_cents=max(payable_cents - paid_cents, 0),
            iva_exempt_discount_cents=to_cents(order.iva_exempt_discount),
            item_totals=(),
        )
    gross_cents = sum(_item_gross_cents(item) for item in items)
    explicit_discount_cents = sum(min(to_cents(item.discount_amount), _item_gross_cents(item)) for item in items)
    fallback_discount_cents = _historical_discount_cents(order, gross_cents, explicit_discount_cents)
    item_totals = calculate_order_item_totals(items, fallback_discount_cents=fallback_discount_cents)
    subtotal_cents = sum(item.gross_cents for item in item_totals)
    discount_cents = sum(item.discount_cents for item in item_totals)
    subtotal_after_discounts_cents = max(subtotal_cents - discount_cents, 0)
    fee_cents = sum(to_cents(fee.total_amount) for fee in order.fees.all())
    taxable_base_cents = subtotal_after_discounts_cents + fee_cents
    tax_cents, total_cents, iva_exempt_discount_cents = _tax_adjusted_totals(taxable_base_cents=taxable_base_cents, order=order)
    paid_cents = _paid_cents(order)
    payable_cents = order.amount_due_cents if respect_locked and order.financial_locked_at and order.amount_due_cents > 0 else total_cents
    amount_due_cents = max(payable_cents - paid_cents, 0)
    return OrderTotals(
        subtotal_cents=subtotal_cents,
        discount_cents=discount_cents + iva_exempt_discount_cents,
        subtotal_after_discounts_cents=subtotal_after_discounts_cents,
        disposable_cents=fee_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        paid_cents=paid_cents,
        amount_due_cents=amount_due_cents,
        iva_exempt_discount_cents=iva_exempt_discount_cents,
        item_totals=item_totals,
    )


def calculate_remaining_balance(order: Order) -> Decimal:
    return calculate_order_totals(order).amount_due


def calculate_person_totals(order: Order, guest: TableGuest) -> dict[str, Any]:
    totals = calculate_order_totals(order)
    guest_items = [
        item_total
        for item_total in totals.item_totals
        if item_total.table_guest_id == guest.id or item_total.guest_number == guest.seat_number
    ]
    total_cents = sum(item.net_cents for item in guest_items)
    from apps.payments.models import PaymentAllocation

    paid_cents = PaymentAllocation.objects.filter(payment__order=order, table_guest=guest).aggregate(total=Sum("amount_cents"))["total"] or 0
    if paid_cents <= 0:
        paid_cents = (
            PaymentAllocation.objects.filter(payment__order=order, guest_number=guest.seat_number).aggregate(total=Sum("amount_cents"))["total"]
            or 0
        )
    return {
        "subtotal": from_cents(sum(item.gross_cents for item in guest_items)),
        "discount_total": from_cents(sum(item.discount_cents for item in guest_items)),
        "total": from_cents(total_cents),
        "paid_total": from_cents(paid_cents),
        "amount_due": from_cents(max(total_cents - int(paid_cents or 0), 0)),
        "item_ids": [item.item_id for item in guest_items],
    }


def calculate_items_remaining_cents(order: Order, item_ids: Iterable[int]) -> int:
    requested_ids = {int(item_id) for item_id in item_ids if str(item_id).isdigit()}
    if not requested_ids:
        return calculate_order_totals(order).amount_due_cents
    totals = calculate_order_totals(order)
    selected_total = sum(item.net_cents for item in totals.item_totals if item.item_id in requested_ids)
    from apps.payments.models import PaymentAllocation

    paid_cents = (
        PaymentAllocation.objects.filter(payment__order=order, order_item_id__in=requested_ids).aggregate(total=Sum("amount_cents"))["total"]
        or 0
    )
    return max(selected_total - int(paid_cents or 0), 0)


def calculate_payment_scope_remaining_cents(order: Order, allocation_payload: dict[str, Any]) -> int:
    scope = str(allocation_payload.get("scope") or "order").strip().lower()
    if scope == "guest":
        table_session = None
        if allocation_payload.get("table_session_id"):
            table_session = TableSession.objects.filter(id=allocation_payload["table_session_id"], primary_order=order).first()
        if table_session is None:
            table_session = TableSession.objects.filter(primary_order=order).order_by("-id").first()
        guest = None
        if allocation_payload.get("table_guest_id"):
            qs = TableGuest.objects.filter(id=allocation_payload["table_guest_id"])
            if table_session:
                qs = qs.filter(session=table_session)
            guest = qs.first()
        if guest is None and table_session and allocation_payload.get("guest_number"):
            guest = TableGuest.objects.filter(session=table_session, seat_number=allocation_payload["guest_number"]).first()
        if guest is None:
            return 0
        return to_cents(calculate_person_totals(order, guest)["amount_due"])
    if scope in {"items", "custom"}:
        return calculate_items_remaining_cents(order, allocation_payload.get("order_item_ids") or [])
    return calculate_order_totals(order).amount_due_cents


def _hydrate_discount_targets(discounts: Iterable[Discount]) -> list[Discount]:
    hydrated = list(discounts)
    for discount in hydrated:
        discount.target_product_ids = set(discount.targets.filter(product__isnull=False).values_list("product_id", flat=True))
        discount.target_category_ids = set(discount.targets.filter(category__isnull=False).values_list("category_id", flat=True))
    return hydrated


def _resolve_snapshot_discount(order: Order, discounts: list[Discount]) -> tuple[Discount | None, bool, str]:
    snapshot = order.discount_snapshot if isinstance(order.discount_snapshot, dict) else {}
    discount_id = snapshot.get("discount_id")
    if not discount_id:
        return None, False, ""
    try:
        discount_id = int(discount_id)
    except (TypeError, ValueError):
        return None, False, ""
    discount = next((candidate for candidate in discounts if candidate.id == discount_id), None)
    if not discount:
        return None, False, ""
    mode = str(snapshot.get("mode") or "").strip().lower()
    return discount, mode == "manual", mode


def apply_order_discounts_and_totals(
    *,
    order: Order,
    order_lines: list[dict[str, Any]],
    service_type_key: str,
    disposable_total: Decimal,
    selected_discount: Discount | None = None,
    force_apply_discount: bool = False,
    discount_mode: str = "",
    manual_discount_snapshot: dict | None = None,
    discounts: Iterable[Discount] | None = None,
) -> Order:
    all_discounts = _hydrate_discount_targets(
        discounts
        if discounts is not None
        else Discount.objects.filter(is_active=True).prefetch_related("targets").order_by("priority", "id")
    )
    if selected_discount is None:
        snapshot_discount, snapshot_force, snapshot_mode = _resolve_snapshot_discount(order, all_discounts)
        selected_discount = snapshot_discount
        force_apply_discount = snapshot_force
        discount_mode = discount_mode or snapshot_mode

    discount_result = apply_discounts(
        order_lines,
        all_discounts,
        service_type_key=service_type_key,
        disposable_total=_money(disposable_total),
        selected_discount=selected_discount,
        force_apply=force_apply_discount,
    )

    line_discount_map = discount_result["line_discounts"]
    for line in order_lines:
        OrderItem.objects.filter(id=line["order_item_id"]).update(
            discount_amount=_money(line_discount_map.get(line["line_key"]) or Decimal("0.00"))
        )

    AppliedDiscount.objects.filter(order=order).delete()
    breakdown_by_discount: dict[int, list[dict[str, Any]]] = {}
    for entry in discount_result["applied_breakdown"]:
        did = entry.get("discount_id")
        breakdown_by_discount.setdefault(did, []).append(entry)

    order_discount_snapshot: dict[str, Any] = {}
    discount_totals = discount_result["discount_totals"]
    subtotal_before_discounts = sum((line["line_total"] for line in order_lines), Decimal("0.00"))
    for discount in all_discounts:
        amount = _money(discount_totals.get(discount.id) or Decimal("0.00"))
        if amount <= 0:
            continue
        applied = AppliedDiscount.objects.create(
            order=order,
            discount_name_snapshot=discount.name,
            discount_type_snapshot=discount.type,
            discount_value_snapshot=discount.value,
            amount_discounted=amount,
            breakdown={"entries": breakdown_by_discount.get(discount.id, [])},
        )
        order_discount_snapshot = {
            "discount_id": discount.id,
            "name": discount.name,
            "type": discount.type,
            "value": str(discount.value),
            "amount": str(applied.amount_discounted),
            "mode": discount_mode or ("manual" if force_apply_discount else "auto"),
            "conditions_met": discount_conditions_met(
                discount,
                service_type_key=service_type_key,
                subtotal_before_discounts=subtotal_before_discounts,
            ),
            "has_conditions": discount_has_conditions(discount),
            "applies_to": discount.applies_to,
            "line_breakdown": breakdown_by_discount.get(discount.id, []),
        }
        if isinstance(manual_discount_snapshot, dict) and order_discount_snapshot["mode"] == "manual":
            order_discount_snapshot["manual_input"] = manual_discount_snapshot

    order.discount_snapshot = order_discount_snapshot
    order.disposable_total = _money(disposable_total)
    return sync_order_totals(order, save=False)


def sync_order_totals(order: Order, *, save: bool = True) -> Order:
    totals = calculate_order_totals(order, respect_locked=False)
    order.subtotal = totals.total
    order.tax = totals.tax_total
    order.total = totals.total
    order.discount_total = totals.discount_total
    order.disposable_total = totals.disposable_total
    order.iva_exempt_discount = totals.iva_exempt_discount
    if order.financial_locked_at is None:
        order.amount_due_cents = totals.total_cents
    if save:
        order.save(
            update_fields=[
                "subtotal",
                "tax",
                "total",
                "discount_total",
                "discount_snapshot",
                "disposable_total",
                "iva_exempt_discount",
                "amount_due_cents",
                "updated_at",
            ]
        )
    return order
