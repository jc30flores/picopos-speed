from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0021_order_pending_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="pending_reference",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
    ]
