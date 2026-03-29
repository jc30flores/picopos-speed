from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0015_orderitem_applied_special_price_rule"),
    ]

    operations = [
        migrations.AlterField(
            model_name="orderitem",
            name="product",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="menu.product"),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="is_custom",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="snapshot_sku_or_code",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="orderinvoice",
            name="sale_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
