from __future__ import annotations

from apps.payments.models import Payment

PAYMENT_METHOD_LABELS = {
    "cash": "Efectivo",
    "card": "Tarjeta",
    "card_debit": "Tarjeta",
    "card_credit": "Tarjeta",
    "transfer": "Transferencia",
    "pedidos_ya": "Pedidos Ya",
    "paypal": "PayPal",
}

PAYMENT_METHOD_ALIASES = {
    "cash": "cash",
    "efectivo": "cash",
    "01": "cash",
    "card": "card",
    "credit_card": "card",
    "debit_card": "card",
    "card_credit": "card",
    "card_debit": "card",
    "credito": "card",
    "debito": "card",
    "credit": "card",
    "debit": "card",
    "transfer": "transfer",
    "bank_transfer": "transfer",
    "pedidosya": "pedidos_ya",
    "pedidos_ya": "pedidos_ya",
    "paypal": "paypal",
}


def normalize_payment_method_code(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    return PAYMENT_METHOD_ALIASES.get(raw, raw)


def payment_code_from_payment(payment: Payment) -> str:
    effective_method = payment.reporting_payment_method if payment.reporting_payment_method_id else payment.payment_method
    code = normalize_payment_method_code(effective_method.code if effective_method else "")
    method = str(payment.method or "").strip().lower()
    if code:
        if code in {"card_credit", "card_debit"}:
            return "card"
        return code
    if method == "cash":
        return "cash"
    if method == "card":
        return "card"
    return "transfer"
