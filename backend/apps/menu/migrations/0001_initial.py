from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ModifierGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("required", models.BooleanField(default=False)),
                ("min_selection", models.PositiveIntegerField(default=0)),
                ("max_selection", models.PositiveIntegerField(default=1)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("image", models.ImageField(blank=True, null=True, upload_to="products/")),
                ("available", models.BooleanField(default=True)),
                (
                    "category",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="products", to="menu.category"),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Modifier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("price", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "group",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="modifiers", to="menu.modifiergroup"),
                ),
            ],
            options={
                "ordering": ["name"],
                "unique_together": {("group", "name")},
            },
        ),
        migrations.CreateModel(
            name="Discount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("description", models.TextField(blank=True)),
                (
                    "type",
                    models.CharField(choices=[("percentage", "Percentage"), ("fixed", "Fixed"), ("happy-hour", "Happy Hour"), ("category", "Category")], max_length=20),
                ),
                ("value", models.DecimalField(decimal_places=2, max_digits=6)),
                (
                    "applies_to",
                    models.CharField(choices=[("ticket", "Ticket"), ("categories", "Categories"), ("products", "Products")], max_length=20),
                ),
                ("days", django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=list, size=None)),
                ("start_time", models.TimeField(blank=True, null=True)),
                ("end_time", models.TimeField(blank=True, null=True)),
                ("min_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("requires_approval", models.BooleanField(default=False)),
                ("auto_apply", models.BooleanField(default=True)),
                ("active", models.BooleanField(default=True)),
                (
                    "service_types",
                    models.ManyToManyField(blank=True, related_name="discounts", to="core.servicetype"),
                ),
                (
                    "target_categories",
                    models.ManyToManyField(blank=True, related_name="discounts", to="menu.category"),
                ),
                (
                    "target_products",
                    models.ManyToManyField(blank=True, related_name="discounts", to="menu.product"),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="product",
            name="modifier_groups",
            field=models.ManyToManyField(blank=True, related_name="products", to="menu.modifiergroup"),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(fields=["category", "available"], name="menu_product_category_38490c_idx"),
        ),
        migrations.AddIndex(
            model_name="discount",
            index=models.Index(fields=["active", "type"], name="menu_discount_active__c4f9aa_idx"),
        ),
        migrations.AddConstraint(
            model_name="modifiergroup",
            constraint=models.CheckConstraint(check=models.Q(("max_selection__gte", models.F("min_selection"))), name="modifier_group_max_gte_min"),
        ),
    ]
