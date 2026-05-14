from __future__ import annotations


CAT017_BY_FISCAL_PAYMENT_TYPE = {
    "CASH": ("01", "Efectivo"),
    "CARD": ("03", "Tarjeta"),
    "TRANSFER": ("05", "Transferencia"),
}


def _normalized(value: str | None) -> str:
    return str(value or "").strip().lower().replace("-", "").replace("_", "").replace(" ", "")


def get_cat017_code_and_label(payment) -> tuple[str, str]:
    raw_method = ""
    method_code = ""
    method_name = ""
    fiscal_payment_type = ""
    if payment is not None:
        raw_method = str(getattr(payment, "method", "") or "").strip()
        payment_method = getattr(payment, "payment_method", None)
        method_code = str(getattr(payment_method, "code", "") or "").strip()
        method_name = str(getattr(payment_method, "name", "") or "").strip()
        fiscal_payment_type = str(getattr(payment_method, "fiscal_payment_type", "") or "").strip().upper()

    if fiscal_payment_type in CAT017_BY_FISCAL_PAYMENT_TYPE:
        code, default_label = CAT017_BY_FISCAL_PAYMENT_TYPE[fiscal_payment_type]
        return code, method_name or default_label

    raw_lower = raw_method.lower()
    normalized_code = _normalized(method_code)
    normalized_name = _normalized(method_name)
    haystack = f"{normalized_code} {normalized_name}"

    if raw_lower in {"cash", "efectivo"} or any(token in haystack for token in {"cash", "efectivo"}):
        return "01", method_name or "Efectivo"

    if raw_lower in {"card_debit", "card_credit", "card"} or any(
        token in haystack
        for token in {
            "carddebit",
            "cardcredit",
            "tarjetadebito",
            "tarjetacredito",
            "debit",
            "credit",
            "debito",
            "credito",
            "card",
            "tarjeta",
            "pedidosya",
            "delivery",
        }
    ):
        return "03", method_name or "Tarjeta"

    if raw_lower in {"transfer", "transferencia"} or any(
        token in haystack for token in {"transfer", "transferencia", "paypal", "applepay", "googlepay", "zelle", "digital"}
    ):
        return "05", method_name or "Transferencia"

    # Never emit invented/custom fiscal payment codes to Hacienda. Unknown custom
    # methods are treated as transfer unless the PaymentMethod category says otherwise.
    raw_name = method_name or raw_method or method_code or "Transferencia"
    return "05", raw_name
