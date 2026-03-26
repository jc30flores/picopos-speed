from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dte", "0010_dteoutbox_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="dterecord",
            name="estado_mh",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="dterecord",
            name="firma",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="dterecord",
            name="mh_response_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="dterecord",
            name="mh_response_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="dterecord",
            name="recibido_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dterecord",
            name="sello_recibido",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]
