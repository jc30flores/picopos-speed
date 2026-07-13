from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0021_appearance_dte_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemappearancesettings",
            name="color_primary_on_light",
            field=models.CharField(default="#1F7A4D", max_length=7),
        ),
        migrations.AddField(
            model_name="systemappearancesettings",
            name="color_primary_on_dark",
            field=models.CharField(default="#1F7A4D", max_length=7),
        ),
    ]
