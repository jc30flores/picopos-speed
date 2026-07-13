from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0026_diningarea_layout_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="kitchen_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendiente"),
                    ("sent", "En cocina"),
                    ("ready", "Listo"),
                    ("delivered", "Entregado"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="kitchen_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="kitchen_ready_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="kitchen_delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="orderitem",
            index=models.Index(fields=["order", "kitchen_status"], name="orders_orde_order_i_42d681_idx"),
        ),
    ]
