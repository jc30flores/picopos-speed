from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0020_order_amount_due_cents_and_financial_locked_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="is_pending",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="pending_marked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="pending_state",
            field=models.CharField(
                choices=[
                    ("none", "No pendiente"),
                    ("pending_payment", "Pendiente de pago"),
                    ("paid_pending_delivery", "Pagada pendiente de entrega"),
                    ("in_kitchen", "En cocina"),
                    ("ready", "Lista"),
                ],
                default="none",
                max_length=30,
            ),
        ),
    ]
