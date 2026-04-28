from django.db import migrations, models


def seed_feature_settings_flags(apps, schema_editor):
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    defaults = [
        ("FF_KIOSK_ENABLED", "KIOSK", "Mostrar u ocultar el módulo KIOSK para todos los usuarios.", True),
        ("FF_CUSTOMER_DISPLAY_ENABLED", "Pantalla Cliente", "Mostrar u ocultar la pantalla cliente para todos los usuarios.", True),
        ("FF_KITCHEN_DISPLAY_ENABLED", "Pantalla Cocina", "Mostrar u ocultar Cocina para todos los usuarios.", True),
        ("FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED", "Totales esperados en cierre de caja", "Controlar visibilidad de totales esperados en cierre de caja.", True),
    ]
    for key, label, description, enabled in defaults:
        FeatureFlag.objects.get_or_create(
            key=key,
            defaults={
                "label": label,
                "description": description,
                "is_enabled": enabled,
                "metadata": {},
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_merge_20260427_2213"),
    ]

    operations = [
        migrations.AddField(
            model_name="featureflag",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(seed_feature_settings_flags, migrations.RunPython.noop),
    ]
