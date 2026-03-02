from django.db import migrations


def safe_rename_and_ensure_index(*, model_name: str, old_name: str, new_name: str, table: str, columns: list[str]):
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    rename_sql = f'''
    DO $$
    BEGIN
      IF to_regclass('public.{old_name}') IS NOT NULL
         AND to_regclass('public.{new_name}') IS NULL THEN
        EXECUTE 'ALTER INDEX "{old_name}" RENAME TO "{new_name}"';
      END IF;
    END $$;
    '''
    reverse_rename_sql = f'''
    DO $$
    BEGIN
      IF to_regclass('public.{new_name}') IS NOT NULL
         AND to_regclass('public.{old_name}') IS NULL THEN
        EXECUTE 'ALTER INDEX "{new_name}" RENAME TO "{old_name}"';
      END IF;
    END $$;
    '''
    create_sql = f'CREATE INDEX CONCURRENTLY IF NOT EXISTS "{new_name}" ON "{table}" ({quoted_columns});'
    drop_sql = f'DROP INDEX CONCURRENTLY IF EXISTS "{new_name}";'

    return migrations.SeparateDatabaseAndState(
        database_operations=[
            migrations.RunSQL(sql=rename_sql, reverse_sql=reverse_rename_sql),
            migrations.RunSQL(sql=create_sql, reverse_sql=drop_sql),
        ],
        state_operations=[
            migrations.RenameIndex(
                model_name=model_name,
                old_name=old_name,
                new_name=new_name,
            ),
        ],
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("core", "0007_taxconfig_tax_included"),
    ]

    operations = [
        safe_rename_and_ensure_index(
            model_name="auditlog",
            old_name="core_auditlog_action_1f4a33_idx",
            new_name="core_auditl_action_d9fb24_idx",
            table="core_auditlog",
            columns=["action"],
        ),
        safe_rename_and_ensure_index(
            model_name="auditlog",
            old_name="core_auditlog_entity__2e93a3_idx",
            new_name="core_auditl_entity__244637_idx",
            table="core_auditlog",
            columns=["entity_type", "entity_id"],
        ),
        safe_rename_and_ensure_index(
            model_name="auditlog",
            old_name="core_auditlog_created_8d5d0a_idx",
            new_name="core_auditl_created_dc23ea_idx",
            table="core_auditlog",
            columns=["created_at"],
        ),
        safe_rename_and_ensure_index(
            model_name="branch",
            old_name="core_branch_code_1f6f10_idx",
            new_name="core_branch_code_b50af7_idx",
            table="core_branch",
            columns=["code"],
        ),
        safe_rename_and_ensure_index(
            model_name="featureflag",
            old_name="core_featureflag_key_idx",
            new_name="core_featur_key_cd102d_idx",
            table="core_featureflag",
            columns=["key"],
        ),
        safe_rename_and_ensure_index(
            model_name="table",
            old_name="core_table_branch__f0c933_idx",
            new_name="core_table_branch__c2f253_idx",
            table="core_table",
            columns=["branch_id", "number"],
        ),
        safe_rename_and_ensure_index(
            model_name="taxconfig",
            old_name="core_taxconfig_is_active_8f9b73_idx",
            new_name="core_taxcon_is_acti_a3cf8c_idx",
            table="core_taxconfig",
            columns=["is_active"],
        ),
    ]
