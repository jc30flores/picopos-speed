from __future__ import annotations

from apps.orders.models import Order


def is_consumer_final_order(order: Order | None) -> bool:
    if not order:
        return True
    customer = getattr(order, "customer", None)
    if not customer:
        return True
    if bool(getattr(customer, "is_consumer_final", False)) or bool(getattr(customer, "is_default_consumer_final", False)):
        return True
    customer_name = str(getattr(customer, "full_name", "") or getattr(customer, "name", "")).strip().upper()
    return customer_name == "CONSUMIDOR FINAL"
