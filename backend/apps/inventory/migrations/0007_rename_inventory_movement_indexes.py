from django.db import migrations, models


INDEX_RENAMES = [
    (
        "inventory_in_movemen_fec5df_idx",
        "inventory_i_movemen_7bd8e8_idx",
        "movement_type, created_at",
    ),
    (
        "inventory_in_referen_fce218_idx",
        "inventory_i_referen_0d8590_idx",
        "reference_type, reference_id",
    ),
    (
        "inventory_in_invento_99f06f_idx",
        "inventory_i_invento_04b724_idx",
        "inventory_item_id, created_at",
    ),
]


def repair_inventory_movement_index_names(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        for old_name, new_name, columns in INDEX_RENAMES:
            cursor.execute(
                f"""
                DO $$
                BEGIN
                    IF to_regclass('public.{old_name}') IS NOT NULL
                       AND to_regclass('public.{new_name}') IS NULL THEN
                        ALTER INDEX public.{old_name} RENAME TO {new_name};
                    ELSIF to_regclass('public.{old_name}') IS NULL
                          AND to_regclass('public.{new_name}') IS NULL THEN
                        CREATE INDEX {new_name}
                        ON public.inventory_inventorymovement ({columns});
                    END IF;
                END $$;
                """
            )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_inventory_advanced"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    repair_inventory_movement_index_names,
                    reverse_code=migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.RenameIndex(
                    model_name="inventorymovement",
                    old_name="inventory_in_movemen_fec5df_idx",
                    new_name="inventory_i_movemen_7bd8e8_idx",
                ),
                migrations.RenameIndex(
                    model_name="inventorymovement",
                    old_name="inventory_in_referen_fce218_idx",
                    new_name="inventory_i_referen_0d8590_idx",
                ),
                migrations.RenameIndex(
                    model_name="inventorymovement",
                    old_name="inventory_in_invento_99f06f_idx",
                    new_name="inventory_i_invento_04b724_idx",
                ),
            ],
        ),
    ]
