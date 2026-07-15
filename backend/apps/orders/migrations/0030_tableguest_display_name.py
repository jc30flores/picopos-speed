from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0029_tablesession_group_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="tableguest",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
    ]
