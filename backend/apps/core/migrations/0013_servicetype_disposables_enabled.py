from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_seed_order_types_and_map_legacy"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicetype",
            name="disposables_enabled",
            field=models.BooleanField(default=False),
        ),
    ]
