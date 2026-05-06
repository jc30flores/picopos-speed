from django.db import migrations, models
from django.utils import timezone
import django.db.models.deletion
from django.db.models import Q


def seed_configurable_payment_methods(apps, schema_editor):
    PaymentMethod = apps.get_model("payments", "PaymentMethod")
    ServiceType = apps.get_model("core", "ServiceType")

    defaults = {
        "cash": {"color_hex": "#16A34A", "is_default": True, "sort_order": 1, "is_cash": True, "name": "Efectivo"},
        "card_debit": {"color_hex": "#2563EB", "sort_order": 2, "name": "Tarjeta Débito"},
        "card_credit": {"color_hex": "#1D4ED8", "sort_order": 3, "name": "Tarjeta Crédito"},
        "transfer": {"color_hex": "#7C3AED", "sort_order": 4, "name": "Transferencia"},
        "pedidos_ya": {"color_hex": "#F97316", "sort_order": 5, "name": "Pedidos Ya"},
        "paypal": {"color_hex": "#0891B2", "sort_order": 6, "name": "PayPal"},
    }
    for code, values in defaults.items():
        PaymentMethod.objects.filter(code=code).update(**values)

    pedidos_type = None
    for service in ServiceType.objects.all():
        normalized = f"{getattr(service, 'key', '')} {getattr(service, 'label', '')}".lower().replace(" ", "").replace("_", "").replace("-", "")
        if "pedidosya" in normalized:
            pedidos_type = service
            break
    if pedidos_type:
        PaymentMethod.objects.filter(code="pedidos_ya").update(auto_select_order_type_id=pedidos_type.id)

    if not PaymentMethod.objects.filter(is_active=True, is_default=True).exists():
        fallback = PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name").first()
        if fallback:
            fallback.is_default = True
            fallback.save(update_fields=["is_default", "updated_at"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_customer_is_iva_exempt"),
        ("payments", "0011_payment_reporting_method_and_changelog"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="color_hex",
            field=models.CharField(blank=True, default="", max_length=7),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="auto_select_order_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="auto_payment_methods",
                to="core.servicetype",
            ),
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="paymentmethod",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="paymentmethod",
            constraint=models.UniqueConstraint(
                fields=("is_default",),
                condition=Q(is_default=True, is_active=True),
                name="unique_active_default_payment_method",
            ),
        ),
        migrations.RunPython(seed_configurable_payment_methods, noop),
    ]
