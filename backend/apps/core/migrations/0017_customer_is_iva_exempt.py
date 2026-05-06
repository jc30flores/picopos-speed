# Generated manually for CF IVA exemption support.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_servicetype_color_hex"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="is_iva_exempt",
            field=models.BooleanField(default=False),
        ),
    ]
