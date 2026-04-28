from django.db import migrations


def seed_flags(apps, schema_editor):
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    FeatureFlag.objects.get_or_create(
        key="FF_CASH_CLOSE_ALLOW_PENDING_ORDERS",
        defaults={
            "label": "Cierre de caja con órdenes pendientes",
            "description": "Permite cerrar caja aunque existan órdenes pendientes.",
            "is_enabled": False,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_featureflag"),
    ]

    operations = [
        migrations.RunPython(seed_flags, migrations.RunPython.noop),
    ]
