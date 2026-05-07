from django.db import migrations, models


def _normalize(value: str) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _fiscal_type_for(method) -> str:
    haystack = _normalize(f"{getattr(method, 'code', '')} {getattr(method, 'name', '')}")
    if getattr(method, "is_cash", False) or any(token in haystack for token in ["cash", "efectivo"]):
        return "CASH"
    if any(token in haystack for token in ["card", "tarjeta", "credito", "crédito", "debito", "débito", "pedidosya", "delivery"]):
        return "CARD"
    if any(token in haystack for token in ["transfer", "transferencia", "paypal", "applepay", "googlepay", "zelle", "digital"]):
        return "TRANSFER"
    return "TRANSFER"


def normalize_payment_methods(apps, schema_editor):
    PaymentMethod = apps.get_model("payments", "PaymentMethod")

    defaults = {
        "cash": {"fiscal_payment_type": "CASH", "is_cash": True, "color_hex": "#16A34A", "sort_order": 1},
        "card": {"fiscal_payment_type": "CARD", "is_cash": False, "color_hex": "#2563EB", "sort_order": 2},
        "card_debit": {"fiscal_payment_type": "CARD", "is_cash": False, "color_hex": "#2563EB", "sort_order": 3},
        "card_credit": {"fiscal_payment_type": "CARD", "is_cash": False, "color_hex": "#1D4ED8", "sort_order": 4},
        "pedidos_ya": {"fiscal_payment_type": "CARD", "is_cash": False, "color_hex": "#F97316", "sort_order": 5},
        "transfer": {"fiscal_payment_type": "TRANSFER", "is_cash": False, "color_hex": "#7C3AED", "sort_order": 6},
        "paypal": {"fiscal_payment_type": "TRANSFER", "is_cash": False, "color_hex": "#0891B2", "sort_order": 7},
    }

    for method in PaymentMethod.objects.all().order_by("sort_order", "id"):
        code = str(method.code or "").strip().lower()
        values = defaults.get(code, {})
        method.fiscal_payment_type = values.get("fiscal_payment_type") or _fiscal_type_for(method)
        method.is_cash = bool(values.get("is_cash", method.fiscal_payment_type == "CASH"))
        if not method.color_hex and values.get("color_hex"):
            method.color_hex = values["color_hex"]
        if values.get("sort_order") is not None and method.sort_order == 0:
            method.sort_order = values["sort_order"]
        if not method.is_active:
            method.is_default = False
            method.auto_select_order_type_id = None
        method.save()

    # Conservative duplicate cleanup: hide exact duplicate active names, preserving the oldest visible row.
    seen_names = set()
    for method in PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "id"):
        key = _normalize(method.name)
        if key and key in seen_names:
            method.is_active = False
            method.is_default = False
            method.auto_select_order_type_id = None
            method.save(update_fields=["is_active", "is_default", "auto_select_order_type", "updated_at"])
        elif key:
            seen_names.add(key)

    PaymentMethod.objects.filter(is_active=False, is_default=True).update(is_default=False)
    defaults_qs = PaymentMethod.objects.filter(is_active=True, is_default=True).order_by("sort_order", "id")
    primary_default = defaults_qs.first()
    if primary_default:
        defaults_qs.exclude(pk=primary_default.pk).update(is_default=False)
    else:
        fallback = PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "id").first()
        if fallback:
            fallback.is_default = True
            fallback.save(update_fields=["is_default", "updated_at"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0012_paymentmethod_configurable_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="fiscal_payment_type",
            field=models.CharField(
                choices=[("CASH", "Efectivo"), ("CARD", "Tarjeta"), ("TRANSFER", "Transferencia")],
                default="TRANSFER",
                max_length=12,
            ),
        ),
        migrations.RunPython(normalize_payment_methods, reverse_noop),
    ]
