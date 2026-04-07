from __future__ import annotations


def get_cat017_code_and_label(payment) -> tuple[str, str]:
    raw_method = ""
    method_code = ""
    if payment is not None:
        raw_method = str(getattr(payment, "method", "") or "").strip()
        payment_method = getattr(payment, "payment_method", None)
        method_code = str(getattr(payment_method, "code", "") or "").strip()

    raw_lower = raw_method.lower()
    normalized_code = method_code.lower().replace("-", "").replace("_", "").replace(" ", "")

    if raw_lower in {"cash", "efectivo"} or normalized_code in {"cash", "efectivo"}:
        return "01", "Efectivo"

    if raw_lower in {"card_debit", "card_credit", "card"} or normalized_code in {
        "carddebit",
        "cardcredit",
        "tarjetadebito",
        "tarjetacredito",
        "debit",
        "credit",
        "card",
        "tarjeta",
    }:
        return "03", "Tarjeta"

    if raw_lower in {"pedidosya", "pedidos_ya", "delivery"} or normalized_code in {"pedidosya", "delivery"}:
        # Pedidos Ya must be reported as card in MH CAT-017 (never transfer).
        return "03", "Pedidos Ya (Tarjeta)"

    if raw_lower in {"transfer", "transferencia"} or normalized_code in {"transfer", "transferencia"}:
        return "05", "Transferencia"

    if raw_lower == "paypal" or normalized_code == "paypal":
        return "05", "PayPal (Transferencia)"

    raw_name = raw_method or method_code or "MEDIO_DESCONOCIDO"
    return "99", f"Otro: {raw_name}"
