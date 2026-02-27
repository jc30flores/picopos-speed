from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0009_modifier_group_pos_toggle_and_name_normalization"),
    ]

    operations = [
        migrations.AddField(
            model_name="discount",
            name="priority",
            field=models.IntegerField(default=100),
        ),
        migrations.AddField(
            model_name="discount",
            name="stackable",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="discount",
            name="bxgy_config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="discount",
            name="type",
            field=models.CharField(choices=[("percent", "Percent"), ("fixed", "Fixed"), ("bxgy", "Buy X Get Y")], max_length=20),
        ),
    ]
