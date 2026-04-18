from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0024_order_whatsapp_num_cliente"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            UPDATE orders_order
            SET whatsapp_num_cliente = ''
            WHERE whatsapp_num_cliente IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
            UPDATE orders_order
            SET whatsapp_num_cliente_country = ''
            WHERE whatsapp_num_cliente_country IS NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AlterField(
            model_name="order",
            name="whatsapp_num_cliente",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AlterField(
            model_name="order",
            name="whatsapp_num_cliente_country",
            field=models.CharField(blank=True, default="", max_length=3),
        ),
    ]
