from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0002_order_discounts"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_status",
            field=models.CharField(
                choices=[("unpaid", "Unpaid"), ("partial", "Partial"), ("paid", "Paid")],
                default="unpaid",
                max_length=20,
            ),
        ),
    ]
