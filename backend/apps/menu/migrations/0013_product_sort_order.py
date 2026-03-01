from django.db import migrations, models


def backfill_product_sort_order(apps, schema_editor):
    """
    Inicializa sort_order por categoría usando orden estable por nombre/id.
    """
    schema_editor.execute(
        """
        WITH ordered AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY category_id ORDER BY name, id) - 1 AS rn
            FROM menu_product
        )
        UPDATE menu_product p
        SET sort_order = o.rn
        FROM ordered o
        WHERE p.id = o.id
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0012_category_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sort_order",
            field=models.PositiveIntegerField(null=True, blank=True, db_index=False),
        ),
        migrations.RunPython(backfill_product_sort_order, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="sort_order",
            field=models.PositiveIntegerField(default=0, db_index=False),
        ),
    ]
