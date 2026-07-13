from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0028_rename_orderitem_kitchen_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="tablesession",
            name="group_number",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
    ]
