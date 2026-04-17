from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0023_order_pending_completion_fields"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name = 'orders_order'
                              AND column_name = 'whatsapp_num_cliente'
                        ) THEN
                            ALTER TABLE orders_order
                                ADD COLUMN whatsapp_num_cliente varchar(32) NOT NULL DEFAULT '';
                        END IF;

                        UPDATE orders_order
                        SET whatsapp_num_cliente = ''
                        WHERE whatsapp_num_cliente IS NULL;

                        ALTER TABLE orders_order
                            ALTER COLUMN whatsapp_num_cliente SET DEFAULT '';

                        ALTER TABLE orders_order
                            ALTER COLUMN whatsapp_num_cliente SET NOT NULL;
                    END
                    $$;
                    """,
                    reverse_sql="""
                    ALTER TABLE orders_order
                        DROP COLUMN IF EXISTS whatsapp_num_cliente;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="order",
                    name="whatsapp_num_cliente",
                    field=models.CharField(blank=True, default="", max_length=32),
                ),
            ],
        ),
    ]
