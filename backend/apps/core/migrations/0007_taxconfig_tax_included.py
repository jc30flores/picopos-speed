from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_featureflag"),
    ]

    operations = [
        migrations.AddField(
            model_name="taxconfig",
            name="tax_included",
            field=models.BooleanField(default=True),
        ),
    ]
