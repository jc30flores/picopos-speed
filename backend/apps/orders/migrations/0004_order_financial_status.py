from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_order_payment_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="financial_status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("paid", "Paid"),
                    ("refunded_partial", "Refunded (Partial)"),
                    ("refunded_full", "Refunded (Full)"),
                    ("voided", "Voided"),
                ],
                default="open",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="refund_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="order",
            name="net_paid",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
