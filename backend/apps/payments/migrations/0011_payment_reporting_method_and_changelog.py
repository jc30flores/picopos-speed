from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0010_payment_split_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="reporting_payment_method",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="payments_reporting_override",
                to="payments.paymentmethod",
            ),
        ),
        migrations.CreateModel(
            name="PaymentMethodChangeLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reason", models.CharField(blank=True, default="", max_length=240)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="payment_method_changes", to=settings.AUTH_USER_MODEL)),
                ("new_payment_method", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="new_payment_method_changes", to="payments.paymentmethod")),
                ("old_payment_method", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="old_payment_method_changes", to="payments.paymentmethod")),
                ("payment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="method_change_logs", to="payments.payment")),
            ],
            options={
                "ordering": ["-changed_at", "-id"],
            },
        ),
    ]
