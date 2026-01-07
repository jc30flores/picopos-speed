from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="taxconfig",
            name="branch",
        ),
        migrations.RemoveField(
            model_name="taxconfig",
            name="effective_from",
        ),
        migrations.AddField(
            model_name="taxconfig",
            name="name",
            field=models.CharField(default="IVA", max_length=80),
        ),
        migrations.AlterField(
            model_name="taxconfig",
            name="rate",
            field=models.DecimalField(decimal_places=4, default=0.13, max_digits=5),
        ),
        migrations.AlterField(
            model_name="taxconfig",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.RemoveIndex(
            model_name="taxconfig",
            name="core_taxconfig_branch__5d60d5_idx",
        ),
        migrations.AddIndex(
            model_name="taxconfig",
            index=models.Index(fields=["is_active"], name="core_taxconfig_is_active_8f9b73_idx"),
        ),
    ]
