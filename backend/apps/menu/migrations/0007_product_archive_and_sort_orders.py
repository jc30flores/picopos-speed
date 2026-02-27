from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0006_product_requires_kitchen"),
    ]

    operations = [
        migrations.AddField(
            model_name="modifier",
            name="sort_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="product",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="modifier_group_order",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
