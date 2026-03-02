from django.db import migrations


def seed_methods(apps, schema_editor):
    PaymentMethod = apps.get_model('payments', 'PaymentMethod')
    defaults = [
        ("CASH", "Efectivo", True, 1),
        ("CARD", "Tarjeta", False, 2),
        ("TRANSFER", "Transferencia", False, 3),
        ("PEDIDOS_YA", "Pedidos Ya", False, 4),
        ("PAYPAL", "PayPal", False, 5),
    ]
    for code, name, is_cash, sort in defaults:
        PaymentMethod.objects.update_or_create(
            code=code,
            defaults={"name": name, "is_cash": is_cash, "sort_order": sort, "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0006_paymentmethod_payment_payment_method_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_methods, migrations.RunPython.noop),
    ]
