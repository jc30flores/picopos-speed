from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("cashier", "0001_initial"),
        ("payments", "0002_payment_cash_session"),
        ("orders", "0003_order_payment_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Refund",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[("cash", "Cash"), ("card", "Card"), ("transfer", "Transfer")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("tip_refunded", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("reason", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_refunds",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "cash_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="refunds",
                        to="cashier.cashsession",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_refunds",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="refunds",
                        to="orders.order",
                    ),
                ),
                (
                    "original_payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="refunds",
                        to="payments.payment",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="refund",
            index=models.Index(fields=["order", "created_at"], name="payments_re_order_i_0d10d8_idx"),
        ),
        migrations.AddIndex(
            model_name="refund",
            index=models.Index(fields=["method"], name="payments_re_method_4b0468_idx"),
        ),
    ]
