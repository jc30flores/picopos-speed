from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Branch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.CharField(max_length=20, unique=True)),
                ("address", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ServiceType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=32, unique=True)),
                ("label", models.CharField(max_length=64)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["label"],
            },
        ),
        migrations.CreateModel(
            name="Table",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.PositiveIntegerField()),
                ("name", models.CharField(blank=True, max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "branch",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tables", to="core.branch"),
                ),
            ],
            options={
                "ordering": ["branch__name", "number"],
                "unique_together": {("branch", "number")},
            },
        ),
        migrations.CreateModel(
            name="TaxConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rate", models.DecimalField(decimal_places=4, max_digits=5)),
                ("is_active", models.BooleanField(default=True)),
                ("effective_from", models.DateField(auto_now_add=True)),
                (
                    "branch",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="tax_config", to="core.branch"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="branch",
            index=models.Index(fields=["code"], name="core_branch_code_1f6f10_idx"),
        ),
        migrations.AddIndex(
            model_name="table",
            index=models.Index(fields=["branch", "number"], name="core_table_branch__f0c933_idx"),
        ),
        migrations.AddIndex(
            model_name="taxconfig",
            index=models.Index(fields=["branch", "is_active"], name="core_taxconfig_branch__5d60d5_idx"),
        ),
    ]
