from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cashier", "0008_cashtransaction_payment_link_and_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashsession",
            name="closing_total_bills",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="closing_total_coins",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
