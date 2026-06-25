from django.db import migrations


def seed_pos_product_images_flag(apps, schema_editor):
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    FeatureFlag.objects.get_or_create(
        key="pos_product_images_enabled",
        defaults={
            "label": "Imágenes de productos en POS",
            "description": "Muestra las imágenes guardadas de los productos en las tarjetas del POS.",
            "is_enabled": False,
            "metadata": {},
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_customer_is_iva_exempt"),
    ]

    operations = [migrations.RunPython(seed_pos_product_images_flag, migrations.RunPython.noop)]
