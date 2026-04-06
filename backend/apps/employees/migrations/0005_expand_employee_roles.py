from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0004_attendance_clock_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="role",
            field=models.CharField(
                choices=[
                    ("cashier", "Cashier"),
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
