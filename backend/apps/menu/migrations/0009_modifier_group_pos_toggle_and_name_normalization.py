from django.db import migrations, models
import django.db.models.deletion
import re


def _normalize(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).upper()


def forwards(apps, schema_editor):
    ModifierGroup = apps.get_model("menu", "ModifierGroup")
    Modifier = apps.get_model("menu", "Modifier")
    ProductModifierGroup = apps.get_model("menu", "ProductModifierGroup")

    for group in ModifierGroup.objects.all():
        normalized = _normalize(group.name)
        if normalized and normalized != group.name:
            group.name = normalized
            group.save(update_fields=["name"])

    for modifier in Modifier.objects.all():
        normalized = _normalize(modifier.name)
        if normalized and normalized != modifier.name:
            modifier.name = normalized
            modifier.save(update_fields=["name"])

    for link in ProductModifierGroup.objects.select_related("modifier_group").all():
        has_paid_options = Modifier.objects.filter(group_id=link.modifier_group_id, price__gt=0).exists()
        link.show_in_pos = has_paid_options
        link.save(update_fields=["show_in_pos"])


def noop(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0008_modifier_images_and_product_disposable"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE menu_product_modifier_groups ADD COLUMN IF NOT EXISTS show_in_pos boolean NOT NULL DEFAULT FALSE;",
                    reverse_sql="ALTER TABLE menu_product_modifier_groups DROP COLUMN IF EXISTS show_in_pos;",
                )
            ],
            state_operations=[
                migrations.CreateModel(
                    name="ProductModifierGroup",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("show_in_pos", models.BooleanField(default=False)),
                        ("modifier_group", models.ForeignKey(db_column="modifiergroup_id", on_delete=django.db.models.deletion.CASCADE, to="menu.modifiergroup")),
                        ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="menu.product")),
                    ],
                    options={
                        "db_table": "menu_product_modifier_groups",
                        "unique_together": {("product", "modifier_group")},
                    },
                ),
                migrations.AlterField(
                    model_name="product",
                    name="modifier_groups",
                    field=models.ManyToManyField(blank=True, related_name="products", through="menu.ProductModifierGroup", through_fields=("product", "modifier_group"), to="menu.modifiergroup"),
                ),
            ],
        ),
        migrations.RunPython(forwards, noop),
    ]
