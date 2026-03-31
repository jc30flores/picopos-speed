from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0018_order_discount_snapshot_and_item_discount_amount"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="send_to_kitchen",
            field=models.BooleanField(default=False),
        ),
    ]
