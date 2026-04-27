from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0006_attendance_cycle_counters"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("clock_in_at", models.DateTimeField()),
                ("break_start_at", models.DateTimeField(blank=True, null=True)),
                ("break_end_at", models.DateTimeField(blank=True, null=True)),
                ("clock_out_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "attendance_record",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cycles", to="employees.attendancerecord"),
                ),
            ],
            options={
                "ordering": ["sequence", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="attendancecycle",
            constraint=models.UniqueConstraint(fields=("attendance_record", "sequence"), name="unique_attendance_cycle_sequence"),
        ),
        migrations.AddIndex(
            model_name="attendancecycle",
            index=models.Index(fields=["attendance_record", "sequence"], name="employees_a_attenda_73f16a_idx"),
        ),
    ]
