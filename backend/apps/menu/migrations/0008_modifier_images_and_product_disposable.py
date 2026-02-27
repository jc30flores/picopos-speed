from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0007_product_archive_and_sort_orders"),
    ]

    operations = [
        migrations.AddField(
            model_name="modifiergroup",
            name="image",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="modifiergroup",
            name="image_path",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="modifier",
            name="image",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="modifier",
            name="image_path",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="product",
            name="disposable_apply_to",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="product",
            name="disposable_fee",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
    ]
