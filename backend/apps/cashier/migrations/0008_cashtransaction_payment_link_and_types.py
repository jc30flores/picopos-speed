from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cashier", "0007_cashtransaction_refund_link"),
        ("payments", "0008_payment_card_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashtransaction",
            name="type",
            field=models.CharField(
                choices=[
                    ("cash_out", "Cash Out"),
                    ("cash_in", "Cash In"),
                    ("expense", "Expense"),
                    ("payout", "Payout"),
                    ("card", "Card"),
                    ("transfer", "Transfer"),
                    ("pedidosya", "PedidosYa"),
                    ("paypal", "PayPal"),
                ],
                default="cash_out",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="cashtransaction",
            name="payment",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="cash_transaction",
                to="payments.payment",
            ),
        ),
    ]
