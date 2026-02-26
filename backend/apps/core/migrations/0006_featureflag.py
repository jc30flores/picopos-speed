from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_merge_0004_auditlog_0004_merge_20251229_1847"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeatureFlag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=80, unique=True)),
                ("label", models.CharField(max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_enabled", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["key"],
                "indexes": [models.Index(fields=["key"], name="core_featureflag_key_idx")],
            },
        ),
    ]
