from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cashier", "0009_cashsession_closing_bills_coins"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashsession",
            name="closing_total_pos_cards",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="cashsession",
            name="closing_total_pedidos_ya",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
