from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0007_order_channel_requires_kitchen_invoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="disposable_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.CreateModel(
            name="OrderFee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fee_type", models.CharField(default="disposable", max_length=40)),
                ("fee_name", models.CharField(max_length=120)),
                ("unit_amount", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("total_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fees", to="orders.order")),
                ("order_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="fees", to="orders.orderitem")),
            ],
        ),
        migrations.AddIndex(
            model_name="orderfee",
            index=models.Index(fields=["order", "fee_type"], name="orders_orde_order_i_524afe_idx"),
        ),
    ]
