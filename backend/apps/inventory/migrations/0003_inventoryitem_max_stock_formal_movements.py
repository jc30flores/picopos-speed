from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_category_links_and_product_overrides"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE inventory_inventoryitem
                        ADD COLUMN IF NOT EXISTS max_stock NUMERIC(12, 3);
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="inventoryitem",
                    name="max_stock",
                    field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
                ),
            ],
        ),
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
                ],
                max_length=32,
            ),
        ),
    ]
