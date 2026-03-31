from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0017_orderitem_unit_price_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="discount_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
