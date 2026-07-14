from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0029_tablesession_group_number"),
        ("payments", "0014_paymentmethod_auto_print_ticket"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_number", models.PositiveIntegerField(blank=True, null=True)),
                ("guest_label", models.CharField(blank=True, default="", max_length=64)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("amount_cents", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment_allocations",
                        to="orders.orderitem",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="allocations",
                        to="payments.payment",
                    ),
                ),
                (
                    "table_guest",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment_allocations",
                        to="orders.tableguest",
                    ),
                ),
                (
                    "table_session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="payment_allocations",
                        to="orders.tablesession",
                    ),
                ),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(
            model_name="paymentallocation",
            index=models.Index(fields=["payment", "created_at"], name="payments_pa_payment_a3c90e_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentallocation",
            index=models.Index(fields=["table_session", "guest_number"], name="payments_pa_table_s_f0c5f2_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentallocation",
            index=models.Index(fields=["table_guest"], name="payments_pa_table_g_2fb5a8_idx"),
        ),
        migrations.AddIndex(
            model_name="paymentallocation",
            index=models.Index(fields=["order_item"], name="payments_pa_order_i_c9b65a_idx"),
        ),
    ]
