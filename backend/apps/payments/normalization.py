from __future__ import annotations

from apps.payments.models import Payment

PAYMENT_METHOD_LABELS = {
    "cash": "Efectivo",
    "card_debit": "Tarjeta Débito",
    "card_credit": "Tarjeta Crédito",
    "transfer": "Transferencia",
    "pedidos_ya": "Pedidos Ya",
    "paypal": "PayPal",
}

PAYMENT_METHOD_ALIASES = {
    "cash": "cash",
    "efectivo": "cash",
    "01": "cash",
    "card": "card_credit",
    "credit_card": "card_credit",
    "debit_card": "card_debit",
    "card_credit": "card_credit",
    "card_debit": "card_debit",
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
    card_type = str(payment.card_type or "").strip().lower()
    if code:
        if code == "card_credit" and card_type == "debit":
            return "card_debit"
        return code
    if method == "cash":
        return "cash"
    if method == "card":
        return "card_debit" if card_type == "debit" else "card_credit"
    return "transfer"
