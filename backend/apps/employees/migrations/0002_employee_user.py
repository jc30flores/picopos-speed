from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("employees", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="employee",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
