from decimal import Decimal

from django.test import TestCase

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Modifier, ModifierGroup, Product
from apps.orders.serializers import OrderCreateSerializer


class PosFastFlowTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Sucursal Centro", code="CENTRO")
        self.service_type = ServiceType.objects.create(key="dine-in", label="En local")
        self.category = Category.objects.create(name="COMIDA")

    def test_pos_fast_mode_autocompletes_required_group_with_default_option(self):
        required_group = ModifierGroup.objects.create(
            name="Arroz",
            required=True,
            min_selection=1,
            max_selection=1,
        )
        free_default = Modifier.objects.create(group=required_group, name="Arroz blanco", price=Decimal("0.00"))
        extra_group = ModifierGroup.objects.create(name="Extras", required=False, min_selection=0, max_selection=3)
        paid_extra = Modifier.objects.create(group=extra_group, name="Queso", price=Decimal("1.50"))
        product = Product.objects.create(
            name="Burrito",
            description="",
            price=Decimal("7.00"),
            category=self.category,
            available=True,
            requires_kitchen=True,
        )
        product.modifier_groups.add(required_group, extra_group)

        serializer = OrderCreateSerializer(
            data={
                "branch_id": self.branch.id,
                "service_type_key": self.service_type.key,
                "source": "pos",
                "channel": "pos",
                "fast_pos_mode": True,
                "items": [
                    {
                        "product_id": product.id,
                        "product_name_snapshot": product.name,
                        "price_snapshot": "7.00",
                        "quantity": 1,
                        "modifiers": [{"id": paid_extra.id}],
                    }
                ],
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        order = serializer.save()
        self.assertEqual(order.channel, "pos")
        self.assertTrue(order.requires_kitchen)
        self.assertEqual(order.total, Decimal("8.50"))

        names = list(order.items.first().applied_modifiers.values_list("modifier_name_snapshot", flat=True))
        self.assertIn(free_default.name, names)
        self.assertIn(paid_extra.name, names)
