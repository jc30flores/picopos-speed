import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_merge_20260111_2141"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="channel",
            field=models.CharField(
                choices=[("pos", "POS"), ("kiosk", "Kiosk"), ("online", "Online")],
                default="pos",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="requires_kitchen",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(
                fields=["channel", "requires_kitchen", "status"],
                name="orders_orde_channel_d7276a_idx",
            ),
        ),
        migrations.CreateModel(
            name="OrderInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("dte_number", models.CharField(blank=True, max_length=80)),
                ("generation_code", models.CharField(blank=True, max_length=120)),
                ("hacienda_payload", models.JSONField(blank=True, default=dict)),
                ("hacienda_response", models.JSONField(blank=True, default=dict)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invoice",
                        to="orders.order",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="orderinvoice",
            index=models.Index(fields=["status", "updated_at"], name="orders_orde_status_81a80a_idx"),
        ),
    ]
