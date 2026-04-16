from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0023_order_pending_completion_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="whatsapp_num_cliente",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.AddField(
            model_name="order",
            name="whatsapp_num_cliente_country",
            field=models.CharField(blank=True, default="", max_length=3),
        ),
    ]
