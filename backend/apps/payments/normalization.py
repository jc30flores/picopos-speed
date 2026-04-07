from __future__ import annotations

from apps.payments.models import Payment, PaymentMethod

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
    "tarjeta": "card",
    "tarjeta_credito": "card",
    "tarjeta_debito": "card",
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


def payment_method_lookup_candidates(value: str | None) -> list[str]:
    normalized = normalize_payment_method_code(value)
    if not normalized:
        return []
    candidates: list[str] = [normalized]
    if normalized == "card":
        candidates.extend(["card_credit", "card_debit", "credit_card", "debit_card", "credit", "debit"])
    return candidates


def resolve_payment_method(value: str | None, *, active_only: bool = True) -> PaymentMethod | None:
    candidates = payment_method_lookup_candidates(value)
    if not candidates:
        return None
    queryset = PaymentMethod.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    methods = list(queryset)
    by_code = {str(method.code or "").strip().lower(): method for method in methods}
    for candidate in candidates:
        found = by_code.get(candidate)
        if found:
            return found
    if normalize_payment_method_code(value) == "card":
        for method in methods:
            normalized_name = str(method.name or "").strip().lower()
            if normalized_name in {"tarjeta", "tarjeta credito", "tarjeta debito"}:
                return method
    return None


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
