from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0008_attendancecycle"),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceBreak",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField(default=1)),
                ("start_at", models.DateTimeField()),
                ("end_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("cycle", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="breaks", to="employees.attendancecycle")),
            ],
            options={"ordering": ["sequence", "id"]},
        ),
        migrations.AddConstraint(
            model_name="attendancebreak",
            constraint=models.UniqueConstraint(fields=("cycle", "sequence"), name="unique_attendance_break_sequence"),
        ),
    ]
