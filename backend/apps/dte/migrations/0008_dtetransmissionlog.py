from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dte", "0007_alter_dtecontrolcounter_establishment_code_and_more"),
        ("orders", "0015_orderitem_applied_special_price_rule"),
        ("core", "0012_seed_order_types_and_map_legacy"),
        ("payments", "0007_seed_payment_methods"),
    ]

    operations = [
        migrations.CreateModel(
            name="DTETransmissionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_status", models.IntegerField(default=0)),
                ("response_body", models.JSONField(blank=True, default=dict)),
                ("success", models.BooleanField(default=False)),
                ("remote_uuid", models.CharField(blank=True, default="", max_length=160)),
                ("sello_recibido", models.CharField(blank=True, default="", max_length=160)),
                ("error_message", models.TextField(blank=True, default="")),
                (
                    "branch",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dte_transmissions", to="core.branch"),
                ),
                (
                    "order",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dte_transmissions", to="orders.order"),
                ),
                (
                    "payment",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dte_transmissions", to="payments.payment"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(model_name="dtetransmissionlog", index=models.Index(fields=["created_at"], name="dte_dtetra_created_b8aeec_idx")),
        migrations.AddIndex(model_name="dtetransmissionlog", index=models.Index(fields=["success"], name="dte_dtetra_success_60327f_idx")),
        migrations.AddIndex(model_name="dtetransmissionlog", index=models.Index(fields=["response_status"], name="dte_dtetra_respons_27d7bf_idx")),
    ]
