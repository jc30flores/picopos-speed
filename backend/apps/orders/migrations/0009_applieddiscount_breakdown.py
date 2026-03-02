from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0008_order_disposable_total_orderfee"),
    ]

    operations = [
        migrations.AddField(
            model_name="applieddiscount",
            name="breakdown",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
