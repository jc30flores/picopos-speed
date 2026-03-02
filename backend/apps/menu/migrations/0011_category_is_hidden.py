from django.db import migrations, models


def hide_archived_category(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')
    Category.objects.filter(name__iexact='SIN CATEGORÍA (ARCHIVADOS)').update(is_hidden=True)


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0010_discount_bxgy_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='is_hidden',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(hide_archived_category, migrations.RunPython.noop),
    ]
