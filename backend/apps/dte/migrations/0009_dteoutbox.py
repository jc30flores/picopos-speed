from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dte", "0008_dtetransmissionlog"),
        ("orders", "0015_orderitem_applied_special_price_rule"),
        ("payments", "0007_seed_payment_methods"),
    ]

    operations = [
        migrations.CreateModel(
            name="DTEOutbox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SENT", "Sent"),
                            ("ACCEPTED", "Accepted"),
                            ("REJECTED", "Rejected"),
                            ("FAILED", "Failed"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("response_status_code", models.IntegerField(blank=True, null=True)),
                ("response_body", models.TextField(blank=True, default="")),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dte_outbox", to="orders.order"),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dte_outbox",
                        to="payments.payment",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="dteoutbox",
            index=models.Index(fields=["status", "created_at"], name="dte_dteoutb_status_02c07a_idx"),
        ),
        migrations.AddIndex(
            model_name="dteoutbox",
            index=models.Index(fields=["order", "status"], name="dte_dteoutb_order_i_85bcc8_idx"),
        ),
        migrations.AddIndex(
            model_name="dteoutbox",
            index=models.Index(fields=["last_attempt_at"], name="dte_dteoutb_last_at_7bab84_idx"),
        ),
    ]
