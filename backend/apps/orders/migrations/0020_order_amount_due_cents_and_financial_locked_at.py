from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0019_order_send_to_kitchen"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="amount_due_cents",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="order",
            name="financial_locked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
