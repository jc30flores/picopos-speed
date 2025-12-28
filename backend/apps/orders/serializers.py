from rest_framework import serializers
from django.db import transaction
from apps.orders.models import Order, OrderItem, AppliedModifier, AppliedDiscount
from apps.menu.models import Product, Modifier, Discount
from apps.core.models import Branch, ServiceType, Table


class AppliedModifierSerializer(serializers.ModelSerializer):
    modifier_id = serializers.PrimaryKeyRelatedField(source="modifier", read_only=True)

    class Meta:
        model = AppliedModifier
        fields = ["id", "modifier_id", "name", "price"]


class OrderItemSerializer(serializers.ModelSerializer):
    applied_modifiers = AppliedModifierSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product_id", "product_name", "price", "quantity", "applied_modifiers"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "customer_name",
            "subtotal",
            "tax",
            "total",
            "service_type_id",
            "branch_id",
            "table_id",
            "created_at",
            "items",
        ]


class AppliedModifierInputSerializer(serializers.Serializer):
    modifier_id = serializers.PrimaryKeyRelatedField(queryset=Modifier.objects.all())
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=8, decimal_places=2)


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    product_name = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    modifiers = AppliedModifierInputSerializer(many=True, required=False)


class AppliedDiscountInputSerializer(serializers.Serializer):
    discount_id = serializers.PrimaryKeyRelatedField(queryset=Discount.objects.all())
    name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderCreateSerializer(serializers.Serializer):
    branch_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)
    service_type_id = serializers.PrimaryKeyRelatedField(queryset=ServiceType.objects.all())
    table_id = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    items = OrderItemInputSerializer(many=True)
    discounts = AppliedDiscountInputSerializer(many=True, required=False)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2)
    total = serializers.DecimalField(max_digits=10, decimal_places=2)

    def _next_order_number(self, branch: Branch) -> int:
        latest = Order.objects.filter(branch=branch).order_by("-order_number").first()
        return (latest.order_number + 1) if latest else 100

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        discounts_data = validated_data.pop("discounts", [])
        branch = validated_data.pop("branch_id", None)
        if branch is None:
            branch = Branch.objects.first()
            if branch is None:
                raise serializers.ValidationError("Branch is required")

        order_number = self._next_order_number(branch)
        order = Order.objects.create(branch=branch, order_number=order_number, **validated_data)

        for item_data in items_data:
            modifiers = item_data.pop("modifiers", [])
            product = item_data.pop("product_id")
            order_item = OrderItem.objects.create(order=order, product=product, **item_data)
            for modifier_data in modifiers:
                AppliedModifier.objects.create(
                    order_item=order_item,
                    modifier=modifier_data["modifier_id"],
                    name=modifier_data["name"],
                    price=modifier_data["price"],
                )

        for discount_data in discounts_data:
            AppliedDiscount.objects.create(
                order=order,
                discount=discount_data["discount_id"],
                name=discount_data["name"],
                amount=discount_data["amount"],
            )

        return order
