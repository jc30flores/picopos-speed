from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0013_paymentmethod_fiscal_type_and_cleanup"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="auto_print_ticket",
            field=models.BooleanField(default=False),
        ),
    ]
