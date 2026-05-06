from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_featureflag_metadata_and_settings_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicetype",
            name="color_hex",
            field=models.CharField(blank=True, max_length=7, null=True),
        ),
    ]
