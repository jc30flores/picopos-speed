from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0004_auditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Register",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "branch",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="registers", to="core.branch"),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="CashSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("opening_cash", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                (
                    "status",
                    models.CharField(choices=[("open", "Open"), ("closed", "Closed")], default="open", max_length=20),
                ),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "closed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="closed_cash_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "opened_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="opened_cash_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "register",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="cashier.register"),
                ),
            ],
            options={
                "ordering": ["-opened_at"],
            },
        ),
        migrations.CreateModel(
            name="CloseoutCount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("counted_cash", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("counted_card", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("counted_transfer", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("counted_tips", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("notes", models.TextField(blank=True)),
                (
                    "cash_session",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="closeout", to="cashier.cashsession"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="register",
            index=models.Index(fields=["branch", "is_active"], name="cashier_re_branch__0b897f_idx"),
        ),
        migrations.AddConstraint(
            model_name="cashsession",
            constraint=models.UniqueConstraint(condition=models.Q(status="open"), fields=("register",), name="unique_open_session_per_register"),
        ),
    ]
