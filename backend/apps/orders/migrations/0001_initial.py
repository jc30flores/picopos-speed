from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        ("menu", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_number", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("preparing", "Preparing"),
                            ("ready", "Ready"),
                            ("delivered", "Delivered"),
                            ("canceled", "Canceled"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("customer_name", models.CharField(blank=True, max_length=120)),
                ("subtotal", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("tax", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "branch",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="core.branch"),
                ),
                (
                    "service_type",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="core.servicetype"),
                ),
                (
                    "table",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="core.table"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "unique_together": {("branch", "order_number")},
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name_snapshot", models.CharField(max_length=160)),
                ("price_snapshot", models.DecimalField(decimal_places=2, max_digits=10)),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order"),
                ),
                (
                    "product",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="menu.product"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="OrderItemModifier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("modifier_name_snapshot", models.CharField(max_length=120)),
                ("modifier_price_snapshot", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                (
                    "order_item",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="applied_modifiers", to="orders.orderitem"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="AppliedDiscount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "discount",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="applied_discounts", to="menu.discount"),
                ),
                (
                    "order",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="applied_discounts", to="orders.order"),
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["status", "created_at"], name="orders_order_status__2272ee_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["branch", "order_number"], name="orders_order_branch__9d4d85_idx"),
        ),
        migrations.AddIndex(
            model_name="orderitem",
            index=models.Index(fields=["order"], name="orders_orderitem_order_i_0dc52b_idx"),
        ),
        migrations.AddIndex(
            model_name="orderitemmodifier",
            index=models.Index(fields=["order_item"], name="orders_orderitemmodi_order__741a7b_idx"),
        ),
        migrations.AddIndex(
            model_name="applieddiscount",
            index=models.Index(fields=["order"], name="orders_applieddiscount_order_i_5e1b9f_idx"),
        ),
    ]
