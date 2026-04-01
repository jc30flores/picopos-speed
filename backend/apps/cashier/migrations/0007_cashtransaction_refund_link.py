from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cashier", "0006_merge_20260401_0533"),
        ("payments", "0008_payment_card_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashtransaction",
            name="refund",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cash_transaction",
                to="payments.refund",
            ),
        ),
    ]
