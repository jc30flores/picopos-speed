from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0009_standardize_payment_method_codes"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="amount_applied",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="payment",
            name="amount_applied_cents",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="payment",
            name="amount_received",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="payment",
            name="amount_received_cents",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="payment",
            name="change_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name="payment",
            name="change_cents",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="payment",
            name="split_part",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="tip_cents",
            field=models.IntegerField(default=0),
        ),
        migrations.RunSQL(
            """
            UPDATE payments_payment
            SET amount_applied = amount,
                amount_received = COALESCE(cash_received, amount + COALESCE(tip_amount, 0)),
                change_amount = GREATEST(COALESCE(cash_received, amount + COALESCE(tip_amount, 0)) - (amount + COALESCE(tip_amount, 0)), 0),
                amount_applied_cents = ROUND(amount * 100),
                amount_received_cents = ROUND(COALESCE(cash_received, amount + COALESCE(tip_amount, 0)) * 100),
                change_cents = ROUND(GREATEST(COALESCE(cash_received, amount + COALESCE(tip_amount, 0)) - (amount + COALESCE(tip_amount, 0)), 0) * 100),
                tip_cents = ROUND(COALESCE(tip_amount, 0) * 100)
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
