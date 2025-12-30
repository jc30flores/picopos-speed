from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("orders", "0002_order_discounts"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Payment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "method",
                    models.CharField(
                        choices=[("cash", "Cash"), ("card", "Card"), ("transfer", "Transfer")],
                        max_length=20,
                    ),
                ),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("tip_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="payments", to="orders.order"),
                ),
                (
                    "received_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="received_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["order", "created_at"], name="payments_payment_order_c54b13_idx"),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["method"], name="payments_payment_method_4c0d39_idx"),
        ),
    ]
