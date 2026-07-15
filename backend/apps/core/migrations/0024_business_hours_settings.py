import datetime

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0023_dte_fiscal_delivery_flags"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessHoursSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("business_hours_enabled", models.BooleanField(default=False)),
                ("opening_time", models.TimeField(default=datetime.time(8, 0))),
                ("closing_time", models.TimeField(default=datetime.time(22, 0))),
                ("grace_hours_after_close", models.PositiveSmallIntegerField(default=4)),
                ("timezone", models.CharField(default="America/El_Salvador", max_length=64)),
                ("auto_close_cash_enabled", models.BooleanField(default=False)),
                ("auto_close_count_zero", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="business_hours_updates",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Business hours settings",
                "verbose_name_plural": "Business hours settings",
            },
        ),
    ]
