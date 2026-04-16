from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0005_expand_employee_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="total_clock_ins",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="total_clock_outs",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
