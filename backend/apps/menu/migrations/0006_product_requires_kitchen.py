from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0005_merge_20260107_2113"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="requires_kitchen",
            field=models.BooleanField(default=False),
        ),
    ]
