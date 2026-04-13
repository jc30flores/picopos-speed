from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0022_order_pending_reference"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="pending_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="pending_completion_note",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="order",
            name="pending_completion_type",
            field=models.CharField(
                choices=[
                    ("none", "Sin finalizar"),
                    ("paid", "Pagada"),
                    ("removed", "Removida"),
                    ("canceled", "Cancelada"),
                ],
                default="none",
                max_length=20,
            ),
        ),
    ]
