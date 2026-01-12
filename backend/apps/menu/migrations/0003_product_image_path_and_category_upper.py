from django.conf import settings
from django.db import migrations, models
from apps.menu.models import product_image_upload_to


def normalize_categories(apps, schema_editor):
    Category = apps.get_model("menu", "Category")
    Product = apps.get_model("menu", "Product")
    DiscountRuleTarget = apps.get_model("menu", "DiscountRuleTarget")

    categories = list(Category.objects.all().order_by("id"))
    normalized_map = {}

    for category in categories:
        normalized = (category.name or "").strip().upper()
        if not normalized:
            normalized = "SIN_CATEGORIA"
        existing = normalized_map.get(normalized)
        if existing:
            Product.objects.filter(category_id=category.id).update(category_id=existing.id)
            DiscountRuleTarget.objects.filter(category_id=category.id).update(category_id=existing.id)
            category.delete()
            continue
        if category.name != normalized:
            Category.objects.filter(id=category.id).update(name=normalized)
        normalized_map[normalized] = category

    for product in Product.objects.exclude(image__isnull=True).exclude(image=""):
        if product.image and getattr(product.image, "name", None):
            Product.objects.filter(id=product.id).update(
                image_path=f"{settings.MEDIA_URL}{product.image.name}"
            )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0002_discount_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image_path",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="product",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to=product_image_upload_to),
        ),
        migrations.RunPython(normalize_categories, reverse_code=noop_reverse),
        migrations.RunSQL(
            sql=(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_menu_categories_name_upper "
                "ON menu_category ((UPPER(TRIM(name))));"
            ),
            reverse_sql="DROP INDEX IF EXISTS ux_menu_categories_name_upper;",
        ),
    ]
