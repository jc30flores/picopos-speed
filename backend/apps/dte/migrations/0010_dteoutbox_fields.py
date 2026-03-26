from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dte", "0009_dteoutbox"),
    ]

    operations = [
        migrations.AddField(
            model_name="dteoutbox",
            name="codigo_generacion",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="dteoutbox",
            name="last_health_body",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="dteoutbox",
            name="last_health_status",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dteoutbox",
            name="next_attempt_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dteoutbox",
            name="numero_control",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="dteoutbox",
            name="payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="dteoutbox",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("SENDING", "Sending"),
                    ("SENT", "Sent"),
                    ("ACCEPTED", "Accepted"),
                    ("REJECTED", "Rejected"),
                    ("FAILED", "Failed"),
                ],
                default="PENDING",
                max_length=16,
            ),
        ),
    ]
