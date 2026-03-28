import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_seed_order_types_and_map_legacy"),
        ("menu", "0018_productspecialpricerule"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceChangeAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("new_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("reason", models.CharField(default="emergency", max_length=40)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("branch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="menu_price_change_audits", to="core.branch")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="price_change_audits", to="menu.product")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="menu_price_change_audits", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["product", "created_at"], name="menu_pricec_product_560d2b_idx"),
                    models.Index(fields=["created_at"], name="menu_pricec_created_1f8c6a_idx"),
                ],
            },
        ),
    ]
