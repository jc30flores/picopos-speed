from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0015_merge_20260301_0607"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="image",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="category",
            name="image_path",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
