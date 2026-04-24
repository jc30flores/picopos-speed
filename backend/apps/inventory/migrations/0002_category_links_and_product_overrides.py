from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
        ("menu", "0020_alter_discount_auto_apply"),
    ]

    operations = [
        migrations.CreateModel(
            name="CategoryInventoryLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_required", models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(0.001)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_links", to="menu.category")),
                ("inventory_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="category_links", to="inventory.inventoryitem")),
            ],
            options={"ordering": ["category_id", "inventory_item_id"], "unique_together": {("category", "inventory_item")}},
        ),
        migrations.CreateModel(
            name="ProductInventoryOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_required", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("is_disabled", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category_link", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_overrides", to="inventory.categoryinventorylink")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_overrides", to="menu.product")),
            ],
            options={"ordering": ["product_id", "category_link_id"], "unique_together": {("product", "category_link")}},
        ),
    ]
