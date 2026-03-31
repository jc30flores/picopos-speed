from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.utils import timezone

from apps.menu.models import Discount


MONEY = Decimal("0.01")


def q2(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _time_in_range(now_t, start_t, end_t) -> bool:
    if not start_t or not end_t:
        return True
    if start_t <= end_t:
        return start_t <= now_t <= end_t
    return now_t >= start_t or now_t <= end_t


@dataclass
class Unit:
    unit_id: str
    line_key: str
    product_id: int
    category_id: int
    base_price: Decimal
    modifier_total: Decimal
    line_item_id: int
    unit_index: int

    def unit_price(self, include_paid_modifiers: bool) -> Decimal:
        return self.base_price + (self.modifier_total if include_paid_modifiers else Decimal("0"))


def discount_has_conditions(discount: Discount) -> bool:
    return bool(
        (discount.service_types or [])
        or (discount.days_of_week or [])
        or discount.start_time
        or discount.end_time
        or discount.min_amount
    )


def discount_conditions_met(discount: Discount, *, service_type_key: str, now=None, subtotal_before_discounts: Decimal = Decimal("0")) -> bool:
    now = now or timezone.localtime(timezone.now())
    day = now.weekday()
    t = now.time()
    if discount.service_types and service_type_key not in discount.service_types:
        return False
    if discount.days_of_week and day not in discount.days_of_week:
        return False
    if not _time_in_range(t, discount.start_time, discount.end_time):
        return False
    if discount.min_amount and subtotal_before_discounts < Decimal(discount.min_amount):
        return False
    return True


def discount_is_eligible(discount: Discount, *, service_type_key: str, now=None, subtotal_before_discounts: Decimal = Decimal("0")) -> bool:
    return discount_conditions_met(
        discount,
        service_type_key=service_type_key,
        now=now,
        subtotal_before_discounts=subtotal_before_discounts,
    )


def _selector_match(unit: Unit, selector: dict[str, Any]) -> bool:
    mode = selector.get("mode")
    if mode == "products":
        return unit.product_id in set(selector.get("product_ids") or [])
    if mode == "categories":
        return unit.category_id in set(selector.get("category_ids") or [])
    return False


def apply_discounts(
    lines: list[dict[str, Any]],
    discounts: list[Discount],
    *,
    service_type_key: str,
    disposable_total: Decimal = Decimal("0"),
    selected_discount: Discount | None = None,
    force_apply: bool = False,
) -> dict[str, Any]:
    subtotal_before_discounts = sum((line["line_total"] for line in lines), Decimal("0"))
    if selected_discount is not None:
        eligible = [selected_discount]
        if not force_apply:
            eligible = [
                selected_discount
                for _ in [0]
                if discount_conditions_met(
                    selected_discount,
                    service_type_key=service_type_key,
                    subtotal_before_discounts=subtotal_before_discounts,
                )
            ]
    else:
        eligible = [
            d for d in discounts
            if d.auto_apply
            and discount_has_conditions(d)
            and discount_is_eligible(d, service_type_key=service_type_key, subtotal_before_discounts=subtotal_before_discounts)
        ]
    eligible.sort(key=lambda d: (d.priority, d.id))
    if eligible:
        eligible = [eligible[0]]

    applied_breakdown: list[dict[str, Any]] = []
    line_discounts: dict[str, Decimal] = {line["line_key"]: Decimal("0") for line in lines}
    discount_totals: dict[int, Decimal] = {}

    def register(discount: Discount, amount: Decimal, payload: dict[str, Any]):
        if amount <= 0:
            return
        discount_totals[discount.id] = discount_totals.get(discount.id, Decimal("0")) + q2(amount)
        applied_breakdown.append({"discount_id": discount.id, "name": discount.name, "amount": str(q2(amount)), **payload})

    non_stackable_applied = False

    for discount in eligible:
        if non_stackable_applied:
            break

        if discount.type in {"percent", "fixed"}:
            for line in lines:
                if discount.applies_to == "products" and line["product_id"] not in discount.target_product_ids:
                    continue
                if discount.applies_to == "categories" and line["category_id"] not in discount.target_category_ids:
                    continue
                if discount.applies_to not in {"products", "categories", "order"}:
                    continue

                base_amount = max(line["line_total"] - line_discounts[line["line_key"]], Decimal("0"))
                if base_amount <= 0:
                    continue
                if discount.applies_to == "order":
                    continue
                if discount.type == "percent":
                    amount = q2(base_amount * (discount.value / Decimal("100")))
                else:
                    amount = min(base_amount, Decimal(discount.value))
                line_discounts[line["line_key"]] += amount
                register(discount, amount, {"scope": "line", "line_key": line["line_key"]})

            if discount.applies_to == "order":
                running_subtotal = sum((line["line_total"] - line_discounts[line["line_key"]] for line in lines), Decimal("0"))
                running_subtotal = max(running_subtotal, Decimal("0"))
                if discount.type == "percent":
                    amount = q2(running_subtotal * (discount.value / Decimal("100")))
                else:
                    amount = min(running_subtotal, Decimal(discount.value))
                if amount > 0 and lines:
                    # apply proportionally for deterministic line totals
                    total_base = sum((line["line_total"] - line_discounts[line["line_key"]] for line in lines), Decimal("0"))
                    remaining = amount
                    for idx, line in enumerate(lines):
                        base = max(line["line_total"] - line_discounts[line["line_key"]], Decimal("0"))
                        if base <= 0:
                            continue
                        if idx == len(lines) - 1 or total_base <= 0:
                            part = remaining
                        else:
                            part = q2(amount * (base / total_base))
                            part = min(part, remaining)
                        line_discounts[line["line_key"]] += part
                        remaining -= part
                    register(discount, amount, {"scope": "order"})

        elif discount.type == "bxgy":
            config = discount.bxgy_config or {}
            global_cfg = config.get("global") or {}
            overlap = bool(global_cfg.get("overlap_buy_get", False))
            rules = config.get("rules") or []

            units: list[Unit] = []
            line_item_counter = 0
            for line in lines:
                for index in range(line["quantity"]):
                    units.append(Unit(
                        unit_id=f"{line['line_key']}-{index}",
                        line_key=line["line_key"],
                        product_id=line["product_id"],
                        category_id=line["category_id"],
                        base_price=line["price_snapshot"],
                        modifier_total=line["modifier_total"],
                        line_item_id=line_item_counter,
                        unit_index=index,
                    ))
                line_item_counter += 1

            consumed_buy: set[str] = set()
            consumed_get: set[str] = set()

            for rule in rules:
                buy = rule.get("buy") or {}
                get = rule.get("get") or {}
                limits = rule.get("limits") or {}
                buy_qty = int(buy.get("qty", 0) or 0)
                get_qty = int(get.get("qty", 0) or 0)
                if buy_qty < 1 or get_qty < 1:
                    continue

                include_mods = bool((get.get("reward") or {}).get("include_paid_modifiers", get.get("include_paid_modifiers", False)))
                buy_selector = buy.get("selector") or {}
                mode = rule.get("mode") or "same_pool"
                get_selector = (get.get("selector") or {}) if mode == "separate_pool" else buy_selector
                reward = get.get("reward") or {}
                apply_to = get.get("apply_to") or "cheapest"
                max_apps = int(limits.get("max_applications_per_ticket", 1) or 1)

                buy_candidates = [u for u in units if _selector_match(u, buy_selector)]
                get_candidates = [u for u in units if _selector_match(u, get_selector)]
                if not buy_candidates or not get_candidates:
                    continue

                price_key = lambda u: (u.unit_price(include_mods), u.line_item_id, u.unit_index)
                get_asc = sorted(get_candidates, key=price_key)
                get_desc = sorted(get_candidates, key=lambda u: (-u.unit_price(include_mods), u.line_item_id, u.unit_index))
                buy_desc = sorted(buy_candidates, key=lambda u: (-u.unit_price(include_mods), u.line_item_id, u.unit_index))

                if mode == "same_pool":
                    pool = sorted(buy_candidates, key=price_key)
                    available_pool = [u for u in pool if u.unit_id not in consumed_buy and u.unit_id not in consumed_get]
                    possible = len(available_pool) // (buy_qty + get_qty)
                    applications = min(possible, max_apps)
                    if applications < 1:
                        continue

                    ranked_pool = sorted(available_pool, key=price_key)
                    ranked_pool_desc = sorted(available_pool, key=lambda u: (-u.unit_price(include_mods), u.line_item_id, u.unit_index))
                    discount_units_needed = applications * get_qty
                    discount_units = ranked_pool[:discount_units_needed] if apply_to == "cheapest" else ranked_pool_desc[:discount_units_needed]
                    discount_unit_ids = {u.unit_id for u in discount_units}

                    if len(discount_units) < discount_units_needed:
                        continue

                    remaining_pool = [u for u in available_pool if u.unit_id not in discount_unit_ids]
                    buy_units_needed = applications * buy_qty
                    selected_buy_units = sorted(remaining_pool, key=lambda u: (-u.unit_price(include_mods), u.line_item_id, u.unit_index))[:buy_units_needed]
                    if len(selected_buy_units) < buy_units_needed:
                        continue

                    for unit in selected_buy_units:
                        consumed_buy.add(unit.unit_id)

                    for unit in discount_units:
                        consumed_get.add(unit.unit_id)
                        unit_price = unit.unit_price(include_mods)
                        reward_type = reward.get("type")
                        reward_value = Decimal(str(reward.get("value", 0) or 0))
                        if reward_type == "percent":
                            amount = q2(unit_price * (reward_value / Decimal("100")))
                        elif reward_type == "fixed_amount":
                            amount = q2(min(unit_price, reward_value))
                        elif reward_type == "fixed_price":
                            amount = q2(max(Decimal("0"), unit_price - reward_value))
                        else:
                            amount = Decimal("0")
                        if amount > 0:
                            line_discounts[unit.line_key] += amount
                            register(
                                discount,
                                amount,
                                {
                                    "scope": "bxgy",
                                    "mode": mode,
                                    "rule_id": rule.get("id"),
                                    "line_key": unit.line_key,
                                    "unit_id": unit.unit_id,
                                },
                            )
                    continue

                applications = 0
                while applications < max_apps:
                    available_buy = [u for u in buy_desc if u.unit_id not in consumed_buy and (overlap or u.unit_id not in consumed_get)]
                    available_get = [u for u in (get_asc if apply_to == "cheapest" else get_desc) if u.unit_id not in consumed_get and (overlap or u.unit_id not in consumed_buy)]
                    if len(available_buy) < buy_qty or len(available_get) < get_qty:
                        break

                    selected_buy = available_buy[:buy_qty]
                    for unit in selected_buy:
                        consumed_buy.add(unit.unit_id)

                    selected_get = available_get[:get_qty]
                    for unit in selected_get:
                        consumed_get.add(unit.unit_id)
                        unit_price = unit.unit_price(include_mods)
                        reward_type = reward.get("type")
                        reward_value = Decimal(str(reward.get("value", 0) or 0))
                        if reward_type == "percent":
                            amount = q2(unit_price * (reward_value / Decimal("100")))
                        elif reward_type == "fixed_amount":
                            amount = q2(min(unit_price, reward_value))
                        elif reward_type == "fixed_price":
                            amount = q2(max(Decimal("0"), unit_price - reward_value))
                        else:
                            amount = Decimal("0")
                        if amount > 0:
                            line_discounts[unit.line_key] += amount
                            register(
                                discount,
                                amount,
                                {
                                    "scope": "bxgy",
                                    "mode": mode,
                                    "rule_id": rule.get("id"),
                                    "line_key": unit.line_key,
                                    "unit_id": unit.unit_id,
                                },
                            )
                    applications += 1

        if not discount.stackable and discount_totals.get(discount.id, Decimal("0")) > 0:
            non_stackable_applied = True

    subtotal_after_discounts = sum((max(line["line_total"] - line_discounts[line["line_key"]], Decimal("0")) for line in lines), Decimal("0"))
    final_subtotal = subtotal_after_discounts + disposable_total

    return {
        "line_discounts": {k: q2(v) for k, v in line_discounts.items()},
        "discount_totals": {k: q2(v) for k, v in discount_totals.items()},
        "applied_breakdown": applied_breakdown,
        "subtotal_after_discounts": q2(subtotal_after_discounts),
        "final_subtotal": q2(final_subtotal),
    }
