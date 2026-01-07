from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0002_taxconfig_update"),
    ]

    operations = [
        migrations.CreateModel(
            name="Employee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=160)),
                ("email", models.EmailField(blank=True, max_length=254, null=True, unique=True)),
                ("phone", models.CharField(blank=True, max_length=40)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("cashier", "Cashier"),
                            ("kitchen", "Kitchen"),
                            ("manager", "Manager"),
                            ("admin", "Admin"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "Active"), ("inactive", "Inactive")],
                        default="active",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "branch",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="employees",
                        to="core.branch",
                    ),
                ),
            ],
            options={
                "ordering": ["full_name"],
            },
        ),
        migrations.CreateModel(
            name="AttendanceRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("check_in", models.DateTimeField(blank=True, null=True)),
                ("check_out", models.DateTimeField(blank=True, null=True)),
                ("minutes_late", models.IntegerField(default=0)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to="employees.employee",
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
            },
        ),
        migrations.CreateModel(
            name="Schedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "schedule_type",
                    models.CharField(
                        choices=[("Fijo", "Fijo"), ("Turnos rotativos", "Turnos rotativos")],
                        default="Fijo",
                        max_length=40,
                    ),
                ),
                ("day_of_week", models.IntegerField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("break_minutes", models.IntegerField(default=0)),
                ("allows_overtime", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "employee",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedules",
                        to="employees.employee",
                    ),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="employee",
            index=models.Index(fields=["branch", "status"], name="employees_em_branch__b6e732_idx"),
        ),
        migrations.AddConstraint(
            model_name="attendancerecord",
            constraint=models.UniqueConstraint(fields=("employee", "date"), name="unique_attendance_employee_date"),
        ),
        migrations.AddIndex(
            model_name="attendancerecord",
            index=models.Index(fields=["employee", "date"], name="employees_at_employee_0f714c_idx"),
        ),
        migrations.AddIndex(
            model_name="schedule",
            index=models.Index(fields=["employee", "day_of_week"], name="employees_sc_employee_d24fbb_idx"),
        ),
    ]
