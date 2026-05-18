from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_category_links_and_product_overrides"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="max_stock",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
        ),
    ]
