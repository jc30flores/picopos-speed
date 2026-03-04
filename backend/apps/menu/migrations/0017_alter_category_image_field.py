from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0016_category_images"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="image",
            field=models.FileField(blank=True, null=True, upload_to="categories/"),
        ),
    ]
