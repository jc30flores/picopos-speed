from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0003_product_image_path_and_category_upper"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="image",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
