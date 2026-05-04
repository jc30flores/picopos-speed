from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0009_attendancebreak'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(model_name='attendancecycle', name='adjusted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='attendancecycle', name='adjusted_by', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_cycles_adjusted', to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name='attendancecycle', name='adjustment_reason', field=models.TextField(blank=True)),
        migrations.AddField(model_name='attendancecycle', name='break_seconds_override', field=models.IntegerField(blank=True, null=True)),
        migrations.CreateModel(
            name='AttendanceCycleAdjustment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('old_clock_in_at', models.DateTimeField(blank=True, null=True)),
                ('new_clock_in_at', models.DateTimeField(blank=True, null=True)),
                ('old_clock_out_at', models.DateTimeField(blank=True, null=True)),
                ('new_clock_out_at', models.DateTimeField(blank=True, null=True)),
                ('old_break_seconds_override', models.IntegerField(blank=True, null=True)),
                ('new_break_seconds_override', models.IntegerField(blank=True, null=True)),
                ('old_computed_break_seconds', models.IntegerField(default=0)),
                ('new_break_seconds', models.IntegerField(default=0)),
                ('reason', models.TextField(blank=True)),
                ('changed_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_cycle_adjustments', to=settings.AUTH_USER_MODEL)),
                ('cycle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='adjustments', to='employees.attendancecycle')),
                ('employee', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='attendance_adjustments', to='employees.employee')),
            ],
        ),
    ]
