from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0016_orderitem_custom_snapshot_and_invoice_sale_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="unit_price_override",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
