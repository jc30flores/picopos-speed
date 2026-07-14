from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0005_superadmin_role"),
    ]

    operations = [
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.CharField(
                choices=[
                    ("superadmin", "Superadmin"),
                    ("admin", "Admin"),
                    ("manager", "Manager"),
                    ("cashier", "Cashier"),
                    ("waiter", "Mesero"),
                    ("kitchen", "Cocina"),
                    ("kiosk", "Kiosk"),
                    ("worker", "Worker"),
                    ("accountant", "Contador"),
                ],
                max_length=20,
            ),
        ),
    ]
