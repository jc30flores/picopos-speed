from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0027_orderitem_kitchen_status"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="orderitem",
            new_name="orders_orde_order_i_8b1d75_idx",
            old_name="orders_orde_order_i_42d681_idx",
        ),
    ]
