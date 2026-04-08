from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0019_pricechangeaudit"),
    ]

    operations = [
        migrations.AlterField(
            model_name="discount",
            name="auto_apply",
            field=models.BooleanField(default=False),
        ),
    ]
