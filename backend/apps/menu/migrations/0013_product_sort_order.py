from django.db import migrations, models


def populate_product_sort_order(apps, schema_editor):
    Product = apps.get_model("menu", "Product")
    for category_id in Product.objects.values_list("category_id", flat=True).distinct():
        products = Product.objects.filter(category_id=category_id).order_by("name", "id")
        for index, product in enumerate(products):
            Product.objects.filter(id=product.id).update(sort_order=index)


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0012_category_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="sort_order",
            field=models.PositiveIntegerField(db_index=True, default=0),
        ),
        migrations.RunPython(populate_product_sort_order, migrations.RunPython.noop),
    ]
