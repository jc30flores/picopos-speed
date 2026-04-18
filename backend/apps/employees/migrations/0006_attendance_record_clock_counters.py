from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("employees", "0005_expand_employee_roles"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE employees_attendancerecord "
                        "ADD COLUMN IF NOT EXISTS total_clock_ins integer"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE employees_attendancerecord "
                        "ADD COLUMN IF NOT EXISTS total_clock_outs integer"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "UPDATE employees_attendancerecord "
                        "SET total_clock_ins = COALESCE(total_clock_ins, 0), "
                        "total_clock_outs = COALESCE(total_clock_outs, 0)"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE employees_attendancerecord "
                        "ALTER COLUMN total_clock_ins SET DEFAULT 0"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE employees_attendancerecord "
                        "ALTER COLUMN total_clock_outs SET DEFAULT 0"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE employees_attendancerecord "
                        "ALTER COLUMN total_clock_ins SET NOT NULL"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
                migrations.RunSQL(
                    sql=(
                        "ALTER TABLE employees_attendancerecord "
                        "ALTER COLUMN total_clock_outs SET NOT NULL"
                    ),
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="attendancerecord",
                    name="total_clock_ins",
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name="attendancerecord",
                    name="total_clock_outs",
                    field=models.IntegerField(default=0),
                ),
            ],
        ),
    ]
