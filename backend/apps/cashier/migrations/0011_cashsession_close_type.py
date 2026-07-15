from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cashier", "0010_cashsession_closing_pos_and_pedidos_ya"),
    ]

    operations = [
        migrations.AddField(
            model_name="cashsession",
            name="close_type",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("automatic_after_hours", "Automático por horario"),
                ],
                default="manual",
                max_length=32,
            ),
        ),
    ]
