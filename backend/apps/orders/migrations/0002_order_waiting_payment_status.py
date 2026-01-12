from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("waiting_payment", "Waiting Payment"),
                    ("new", "New"),
                    ("preparing", "Preparing"),
                    ("ready", "Ready"),
                    ("delivered", "Delivered"),
                    ("canceled", "Canceled"),
                ],
                default="waiting_payment",
                max_length=20,
            ),
        ),
    ]
