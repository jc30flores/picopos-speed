from django.db import migrations


def standardize_payment_methods(apps, schema_editor):
    PaymentMethod = apps.get_model("payments", "PaymentMethod")
    Payment = apps.get_model("payments", "Payment")
    Refund = apps.get_model("payments", "Refund")

    canonical = [
        ("cash", "Efectivo", True, 1),
        ("card_debit", "Tarjeta Débito", False, 2),
        ("card_credit", "Tarjeta Crédito", False, 3),
        ("transfer", "Transferencia", False, 4),
        ("pedidos_ya", "Pedidos Ya", False, 5),
        ("paypal", "PayPal", False, 6),
    ]

    for code, name, is_cash, sort in canonical:
        PaymentMethod.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_cash": is_cash, "sort_order": sort, "is_active": True},
        )

    legacy = {
        "CASH": "cash",
        "CARD": "card_credit",
        "TRANSFER": "transfer",
        "PEDIDOS_YA": "pedidos_ya",
        "PAYPAL": "paypal",
    }

    id_by_code = {pm.code: pm.id for pm in PaymentMethod.objects.all()}

    for old_code, new_code in legacy.items():
        old = PaymentMethod.objects.filter(code=old_code).first()
        if not old:
            continue
        target_id = id_by_code.get(new_code)
        if target_id:
            Payment.objects.filter(payment_method_id=old.id).update(payment_method_id=target_id)
            Refund.objects.filter(payment_method_id=old.id).update(payment_method_id=target_id)
        old.is_active = False
        old.save(update_fields=["is_active"])

    Payment.objects.filter(payment_method__isnull=True, method="card", card_type="debit").update(payment_method_id=id_by_code["card_debit"])
    Payment.objects.filter(payment_method__isnull=True, method="card").exclude(card_type="debit").update(payment_method_id=id_by_code["card_credit"])
    Payment.objects.filter(payment_method__isnull=True, method="cash").update(payment_method_id=id_by_code["cash"])
    Payment.objects.filter(payment_method__isnull=True, method="transfer").update(payment_method_id=id_by_code["transfer"])


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0008_payment_card_type"),
    ]

    operations = [
        migrations.RunPython(standardize_payment_methods, migrations.RunPython.noop),
    ]
