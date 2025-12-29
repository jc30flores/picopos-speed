from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="discount_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["created_at"], name="orders_order_created_at_75b490_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["service_type"], name="orders_order_service_type_1a9f1b_idx"),
        ),
        migrations.RemoveField(
            model_name="applieddiscount",
            name="discount",
        ),
        migrations.RemoveField(
            model_name="applieddiscount",
            name="name",
        ),
        migrations.RemoveField(
            model_name="applieddiscount",
            name="amount",
        ),
        migrations.AddField(
            model_name="applieddiscount",
            name="discount_name_snapshot",
            field=models.CharField(default="", max_length=160),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applieddiscount",
            name="discount_type_snapshot",
            field=models.CharField(default="", max_length=20),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="applieddiscount",
            name="discount_value_snapshot",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="applieddiscount",
            name="amount_discounted",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
