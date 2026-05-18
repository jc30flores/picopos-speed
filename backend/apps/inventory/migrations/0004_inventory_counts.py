from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0003_inventoryitem_max_stock_formal_movements"),
    ]

    operations = [
        migrations.AlterField(
            model_name="inventorymovement",
            name="movement_type",
            field=models.CharField(
                choices=[
                    ("initial_stock", "Stock inicial"),
                    ("stock_add", "Entrada"),
                    ("stock_adjustment", "Ajuste"),
                    ("sale_deduction", "Descuento por venta"),
                    ("reversal", "Reversión"),
                    ("inventory_entry", "Entrada de producto"),
                    ("inventory_loss", "Pérdida"),
                    ("inventory_damaged", "Producto dañado"),
                    ("inventory_correction", "Corrección de stock"),
                    ("inventory_count_adjustment", "Ajuste por conteo"),
                ],
                max_length=32,
            ),
        ),
        migrations.CreateModel(
            name="InventoryCountSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(blank=True, default="", max_length=32, unique=True)),
                ("count_type", models.CharField(choices=[("complete", "Conteo completo"), ("manual", "Conteo manual"), ("category", "Conteo por categoría")], default="manual", max_length=16)),
                ("status", models.CharField(choices=[("draft", "Borrador"), ("in_progress", "En progreso"), ("finalized", "Finalizado"), ("applied", "Aplicado"), ("cancelled", "Cancelado")], default="draft", max_length=16)),
                ("notes", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_reason", models.CharField(blank=True, default="", max_length=255)),
                ("total_items", models.PositiveIntegerField(default=0)),
                ("counted_items", models.PositiveIntegerField(default=0)),
                ("total_differences", models.PositiveIntegerField(default=0)),
                ("total_positive_differences", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("total_negative_differences", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("applied_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_counts_applied", to=settings.AUTH_USER_MODEL)),
                ("cancelled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_counts_cancelled", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_counts_created", to=settings.AUTH_USER_MODEL)),
                ("finalized_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="inventory_counts_finalized", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["status", "created_at"], name="inventory_i_status_fecf3b_idx"), models.Index(fields=["count_type", "created_at"], name="inventory_i_count_t_11a07a_idx"), models.Index(fields=["code"], name="inventory_i_code_2e9c5b_idx")],
            },
        ),
        migrations.CreateModel(
            name="InventoryCountLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("system_stock", models.DecimalField(decimal_places=3, max_digits=12)),
                ("counted_stock", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("difference", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("note", models.CharField(blank=True, default="", max_length=255)),
                ("stock_before_apply", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("stock_after_apply", models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("inventory_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="count_lines", to="inventory.inventoryitem")),
                ("movement", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="count_lines", to="inventory.inventorymovement")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="inventory.inventorycountsession")),
            ],
            options={
                "ordering": ["inventory_item__name", "id"],
                "unique_together": {("session", "inventory_item")},
                "indexes": [models.Index(fields=["session", "inventory_item"], name="inventory_i_session_0c2cf0_idx")],
            },
        ),
    ]
