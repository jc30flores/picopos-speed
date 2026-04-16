from __future__ import annotations

from apps.orders.models import Order


def is_consumer_final_order(order: Order | None) -> bool:
    if order is None:
        return True
    customer = getattr(order, "customer", None)
    if customer is not None:
        if bool(getattr(customer, "is_consumer_final", False)):
            return True
        client_type = str(getattr(customer, "client_type", "") or "").strip().upper()
        if client_type and client_type != "CF":
            return False
    dte_document_type = str(getattr(order, "dte_document_type", "CF") or "CF").strip().upper()
    return dte_document_type == "CF"
