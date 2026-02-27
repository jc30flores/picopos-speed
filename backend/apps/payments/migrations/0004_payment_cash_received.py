from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0003_refund"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="cash_received",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
