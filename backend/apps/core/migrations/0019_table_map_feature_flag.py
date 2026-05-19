from django.db import migrations


def seed_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    FeatureFlag.objects.get_or_create(
        key="table_map_enabled",
        defaults={
            "label": "Mapa de mesas",
            "description": "Activa el modo restaurante con mapa de mesas, editor de salón y órdenes por mesa.",
            "is_enabled": False,
            "metadata": {},
        },
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0018_pos_product_images_feature_flag")]
    operations = [migrations.RunPython(seed_flag, migrations.RunPython.noop)]
