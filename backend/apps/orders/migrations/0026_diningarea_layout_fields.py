from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0025_table_map_models"),
    ]

    operations = [
        migrations.AddField(model_name="diningarea", name="x", field=models.FloatField(default=0)),
        migrations.AddField(model_name="diningarea", name="y", field=models.FloatField(default=0)),
        migrations.AddField(model_name="diningarea", name="width", field=models.FloatField(default=320)),
        migrations.AddField(model_name="diningarea", name="height", field=models.FloatField(default=220)),
        migrations.AddField(model_name="diningarea", name="color", field=models.CharField(max_length=20, blank=True, default="")),
        migrations.AddField(model_name="diningarea", name="operational_zoom", field=models.FloatField(default=1)),
        migrations.AddField(model_name="diningarea", name="operational_offset_x", field=models.FloatField(default=0)),
        migrations.AddField(model_name="diningarea", name="operational_offset_y", field=models.FloatField(default=0)),
    ]
