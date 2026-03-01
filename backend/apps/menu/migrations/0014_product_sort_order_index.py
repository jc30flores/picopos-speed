from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("menu", "0013_product_sort_order"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                "menu_product_sort_order_idx ON menu_product (sort_order);"
            ),
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS menu_product_sort_order_idx;",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="product",
                    name="sort_order",
                    field=models.PositiveIntegerField(default=0, db_index=True),
                ),
            ],
        ),
    ]
