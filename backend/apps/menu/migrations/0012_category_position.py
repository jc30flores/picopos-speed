from django.db import migrations, models


def populate_category_positions(apps, schema_editor):
    Category = apps.get_model('menu', 'Category')
    for index, category in enumerate(Category.objects.all().order_by('name', 'id')):
        Category.objects.filter(id=category.id).update(position=index)


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0011_category_is_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='position',
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(populate_category_positions, migrations.RunPython.noop),
    ]
