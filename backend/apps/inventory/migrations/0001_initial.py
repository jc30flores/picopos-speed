from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("menu", "0020_alter_discount_auto_apply"),
        ("orders", "0024_order_whatsapp_num_cliente_default"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("sku", models.CharField(blank=True, default="", max_length=80)),
                ("unit", models.CharField(default="unidad", max_length=24)),
                ("current_stock", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("min_stock", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("notes", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="InventorySaleApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("applied_at", models.DateTimeField(auto_now_add=True)),
                ("applied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_application", to="orders.order")),
            ],
            options={"ordering": ["-applied_at"]},
        ),
        migrations.CreateModel(
            name="InventoryMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("movement_type", models.CharField(choices=[("initial_stock", "Stock inicial"), ("stock_add", "Entrada"), ("stock_adjustment", "Ajuste"), ("sale_deduction", "Descuento por venta"), ("reversal", "Reversión")], max_length=32)),
                ("quantity_change", models.DecimalField(decimal_places=3, max_digits=12)),
                ("quantity_before", models.DecimalField(decimal_places=3, max_digits=12)),
                ("quantity_after", models.DecimalField(decimal_places=3, max_digits=12)),
                ("reference_type", models.CharField(blank=True, default="", max_length=32)),
                ("reference_id", models.CharField(blank=True, default="", max_length=64)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("inventory_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movements", to="inventory.inventoryitem")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="CatalogProductInventoryLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_required", models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(0.001)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("catalog_product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_links", to="menu.product")),
                ("inventory_item", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="product_links", to="inventory.inventoryitem")),
            ],
            options={"ordering": ["catalog_product_id", "inventory_item_id"], "unique_together": {("catalog_product", "inventory_item")}},
        ),
        migrations.AddIndex(model_name="inventoryitem", index=models.Index(fields=["name"], name="inventory_in_name_6ab43c_idx")),
        migrations.AddIndex(model_name="inventoryitem", index=models.Index(fields=["sku"], name="inventory_in_sku_30780b_idx")),
        migrations.AddIndex(model_name="inventorymovement", index=models.Index(fields=["movement_type", "created_at"], name="inventory_in_movemen_fec5df_idx")),
        migrations.AddIndex(model_name="inventorymovement", index=models.Index(fields=["reference_type", "reference_id"], name="inventory_in_referen_fce218_idx")),
        migrations.AddIndex(model_name="inventorymovement", index=models.Index(fields=["inventory_item", "created_at"], name="inventory_in_invento_99f06f_idx")),
    ]
