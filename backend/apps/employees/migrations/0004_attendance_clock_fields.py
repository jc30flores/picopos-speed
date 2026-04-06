from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0003_rename_employees_at_employee_0f714c_idx_employees_a_employe_db3be2_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="break_end",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="break_start",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="clock_in",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="clock_out",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="attendancerecord",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
