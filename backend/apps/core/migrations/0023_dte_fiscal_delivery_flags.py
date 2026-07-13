from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0022_appearance_on_light_dark"),
    ]

    operations = [
        migrations.AddField(
            model_name="dteglobalsettings",
            name="fiscal_email_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="dteglobalsettings",
            name="fiscal_json_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="dteglobalsettings",
            name="fiscal_pdf_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="dteglobalsettings",
            name="fiscal_whatsapp_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
