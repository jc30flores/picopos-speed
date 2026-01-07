from django.db import migrations, models
import django.contrib.postgres.fields
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="discount",
            name="service_types",
        ),
        migrations.RemoveField(
            model_name="discount",
            name="target_categories",
        ),
        migrations.RemoveField(
            model_name="discount",
            name="target_products",
        ),
        migrations.RemoveField(
            model_name="discount",
            name="days",
        ),
        migrations.RemoveField(
            model_name="discount",
            name="requires_approval",
        ),
        migrations.RemoveField(
            model_name="discount",
            name="active",
        ),
        migrations.AddField(
            model_name="discount",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="discount",
            name="service_types",
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=32), default=list, size=None, blank=True),
        ),
        migrations.AddField(
            model_name="discount",
            name="days_of_week",
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), default=list, size=None, blank=True),
        ),
        migrations.AlterField(
            model_name="discount",
            name="type",
            field=models.CharField(choices=[("percent", "Percent"), ("fixed", "Fixed")], max_length=20),
        ),
        migrations.AlterField(
            model_name="discount",
            name="applies_to",
            field=models.CharField(choices=[("order", "Order"), ("products", "Products"), ("categories", "Categories")], max_length=20),
        ),
        migrations.AlterField(
            model_name="discount",
            name="min_amount",
            field=models.DecimalField(decimal_places=2, max_digits=10, null=True, blank=True),
        ),
        migrations.AddIndex(
            model_name="discount",
            index=models.Index(fields=["is_active", "type"], name="menu_discount_is_active_2b2d8b_idx"),
        ),
        migrations.CreateModel(
            name="DiscountRuleTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "category",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="menu.category"),
                ),
                (
                    "product",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="menu.product"),
                ),
                (
                    "discount",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="menu.discount"),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="discountruletarget",
            constraint=models.CheckConstraint(
                check=models.Q(product__isnull=False, category__isnull=True)
                | models.Q(product__isnull=True, category__isnull=False),
                name="discount_rule_target_product_or_category",
            ),
        ),
    ]
