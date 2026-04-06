from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_userprofile_pin_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("manager", "Manager"),
                    ("cashier", "Cashier"),
                    ("kitchen", "Cocina"),
                    ("kiosk", "Kiosk"),
                    ("worker", "Worker"),
                    ("accountant", "Contador"),
                ],
                max_length=20,
            ),
        ),
    ]
