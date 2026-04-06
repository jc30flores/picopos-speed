from __future__ import annotations


def get_cat017_code_and_label(payment) -> tuple[str, str]:
    raw_method = ""
    method_code = ""
    card_type = ""

    if payment is not None:
        raw_method = str(getattr(payment, "method", "") or "").strip()
        card_type = str(getattr(payment, "card_type", "") or "").strip().lower()
        payment_method = getattr(payment, "payment_method", None)
        method_code = str(getattr(payment_method, "code", "") or "").strip()

    raw_lower = raw_method.lower()
    normalized_code = method_code.lower().replace("-", "").replace("_", "").replace(" ", "")

    if raw_lower in {"cash", "efectivo"} or normalized_code in {"cash", "efectivo"}:
        return "01", "Efectivo"

    if raw_lower == "card_debit" or normalized_code in {"carddebit", "tarjetadebito", "debit"}:
        return "02", "Tarjeta Débito"

    if raw_lower == "card_credit" or normalized_code in {"cardcredit", "tarjetacredito", "credit"}:
        return "03", "Tarjeta Crédito"

    if raw_lower == "card" or normalized_code in {"card", "tarjeta"}:
        return ("03", "Tarjeta Crédito") if card_type == "credit" else ("02", "Tarjeta Débito")

    if raw_lower in {"pedidosya", "pedidos_ya"} or normalized_code in {"pedidosya"}:
        # Pedidos Ya must be reported as card in MH CAT-017 (never transfer).
        return "03", "Pedidos Ya (Tarjeta Crédito)"

    if raw_lower in {"transfer", "transferencia"} or normalized_code in {"transfer", "transferencia"}:
        return "05", "Transferencia"

    if raw_lower == "paypal" or normalized_code == "paypal":
        return "05", "PayPal (Transferencia)"

    raw_name = raw_method or method_code or "MEDIO_DESCONOCIDO"
    return "99", f"Otro: {raw_name}"
