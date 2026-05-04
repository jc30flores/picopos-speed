from django.db import migrations, models


def mark_deleted_employees(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    Employee.objects.filter(full_name__istartswith='Empleado eliminado').update(is_deleted=True, status='inactive')


class Migration(migrations.Migration):
    dependencies = [
        ('employees', '0010_attendancecycle_adjustments'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_deleted_employees, migrations.RunPython.noop),
    ]
