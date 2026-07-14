from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0011_employee_is_deleted_cleanup"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="role",
            field=models.CharField(
                choices=[
                    ("cashier", "Cashier"),
                    ("waiter", "Mesero"),
                    ("kitchen", "Cocina"),
                    ("manager", "Manager"),
                    ("admin", "Admin"),
                    ("kiosk", "Kiosk"),
                    ("worker", "Worker"),
                ],
                max_length=20,
            ),
        ),
    ]
