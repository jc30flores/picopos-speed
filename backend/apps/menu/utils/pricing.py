from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from django.utils import timezone

from apps.core.models import ServiceType
from apps.menu.models import Product, ProductSpecialPriceRule


@dataclass
class EffectivePriceResult:
    effective_price: Decimal
    applied_rule: ProductSpecialPriceRule | None


def _normalize_dt(at: datetime | None) -> datetime:
    now = at or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())
    return timezone.localtime(now)


def _matches_time_range(current: time, start_time: time | None, end_time: time | None) -> bool:
    if not start_time and not end_time:
        return True
    if start_time and not end_time:
        return current >= start_time
    if end_time and not start_time:
        return current <= end_time
    assert start_time is not None and end_time is not None
    if start_time <= end_time:
        return start_time <= current <= end_time
    return current >= start_time or current <= end_time


def _matches_rule(rule: ProductSpecialPriceRule, *, at: datetime, order_type: ServiceType | None) -> bool:
    current_date = at.date()
    current_time = at.timetz().replace(tzinfo=None)

    if rule.start_date and current_date < rule.start_date:
        return False
    if rule.end_date and current_date > rule.end_date:
        return False

    if rule.days_of_week:
        if at.weekday() not in set(int(day) for day in rule.days_of_week):
            return False

    if not _matches_time_range(current_time, rule.start_time, rule.end_time):
        return False

    if not rule.applies_to_all_order_types:
        if order_type is None:
            return False
        allowed_ids = {item.id for item in rule.order_types.all()}
        if order_type.id not in allowed_ids:
            return False

    return True


def _calculate_rule_price(base_price: Decimal, rule: ProductSpecialPriceRule) -> Decimal:
    if rule.discount_type == ProductSpecialPriceRule.DISCOUNT_TYPE_FIXED_PRICE:
        if rule.fixed_price is None:
            return base_price
        candidate = Decimal(rule.fixed_price)
    else:
        if rule.percent_off is None:
            return base_price
        candidate = base_price * (Decimal("1") - (Decimal(rule.percent_off) / Decimal("100")))
    if candidate < 0:
        candidate = Decimal("0")
    return candidate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _rule_specificity(rule: ProductSpecialPriceRule) -> tuple[int, int, int, int]:
    return (
        int(not rule.applies_to_all_order_types),
        int(bool(rule.start_date or rule.end_date)),
        int(bool(rule.start_time or rule.end_time)),
        int(bool(rule.days_of_week)),
    )


def _normalize_sort_dt(value: datetime | None) -> datetime:
    if value is None:
        return timezone.make_aware(datetime.min, timezone.get_current_timezone())
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _rule_sort_key(rule: ProductSpecialPriceRule) -> tuple[float | int, ...]:
    order_type_specific, has_date_range, has_time_range, has_days = _rule_specificity(rule)
    return (
        -rule.priority,
        -order_type_specific,
        -has_date_range,
        -has_time_range,
        -has_days,
        -_normalize_sort_dt(rule.updated_at).timestamp(),
        -_normalize_sort_dt(rule.created_at).timestamp(),
        -rule.id,
    )


def resolve_effective_price(
    product: Product,
    *,
    order_type: ServiceType | None = None,
    at: datetime | None = None,
    rules: Iterable[ProductSpecialPriceRule] | None = None,
) -> EffectivePriceResult:
    normalized_at = _normalize_dt(at)
    base_price = Decimal(product.price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rule_pool = list(rules) if rules is not None else list(
        product.special_price_rules.filter(is_active=True).prefetch_related("order_types")
    )

    matched: list[tuple[ProductSpecialPriceRule, Decimal]] = []
    for rule in rule_pool:
        if not rule.is_active:
            continue
        if _matches_rule(rule, at=normalized_at, order_type=order_type):
            matched.append((rule, _calculate_rule_price(base_price, rule)))

    if not matched:
        return EffectivePriceResult(effective_price=base_price, applied_rule=None)

    matched.sort(key=lambda item: _rule_sort_key(item[0]))
    chosen_rule, chosen_price = matched[0]
    return EffectivePriceResult(effective_price=chosen_price, applied_rule=chosen_rule)
