from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0019_table_map_feature_flag")]

    operations = [
        migrations.CreateModel(
            name="TicketSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ticket_logo", models.FileField(blank=True, null=True, upload_to="ticket_logos/")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Ticket settings",
                "verbose_name_plural": "Ticket settings",
            },
        ),
    ]
