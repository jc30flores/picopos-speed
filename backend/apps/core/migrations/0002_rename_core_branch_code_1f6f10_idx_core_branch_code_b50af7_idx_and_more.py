from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE indexname = 'core_branch_code_1f6f10_idx'
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE indexname = 'core_branch_code_b50af7_idx'
                ) THEN
                    ALTER INDEX core_branch_code_1f6f10_idx RENAME TO core_branch_code_b50af7_idx;
                END IF;
            END $$;
            """,
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE indexname = 'core_branch_code_b50af7_idx'
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM pg_indexes
                    WHERE indexname = 'core_branch_code_1f6f10_idx'
                ) THEN
                    ALTER INDEX core_branch_code_b50af7_idx RENAME TO core_branch_code_1f6f10_idx;
                END IF;
            END $$;
            """,
        ),
    ]
