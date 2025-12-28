from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from apps.orders.models import Order, OrderItem, OrderItemModifier, AppliedDiscount
from apps.menu.models import Product, Discount
from apps.core.models import Branch, ServiceType, Table, TaxConfig


class OrderItemModifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemModifier
        fields = ["id", "modifier_name_snapshot", "modifier_price_snapshot"]


class OrderItemSerializer(serializers.ModelSerializer):
    applied_modifiers = OrderItemModifierSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name_snapshot",
            "price_snapshot",
            "quantity",
            "applied_modifiers",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    service_type = serializers.CharField(source="service_type.key", read_only=True)

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
            "service_type",
            "branch_id",
            "table_id",
            "created_at",
            "items",
        ]


class AppliedModifierInputSerializer(serializers.Serializer):
    name = serializers.CharField()
    price = serializers.DecimalField(max_digits=8, decimal_places=2)


class OrderItemInputSerializer(serializers.Serializer):
    product_id = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    product_name_snapshot = serializers.CharField()
    price_snapshot = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField(min_value=1)
    modifiers = AppliedModifierInputSerializer(many=True, required=False)


class AppliedDiscountInputSerializer(serializers.Serializer):
    discount_id = serializers.PrimaryKeyRelatedField(queryset=Discount.objects.all())
    name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class OrderCreateSerializer(serializers.Serializer):
    branch_id = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)
    service_type_key = serializers.CharField()
    table_id = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), required=False, allow_null=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    items = OrderItemInputSerializer(many=True)
    discounts = AppliedDiscountInputSerializer(many=True, required=False)

    def _next_order_number(self, branch: Branch) -> int:
        latest = Order.objects.filter(branch=branch).order_by("-order_number").first()
        return (latest.order_number + 1) if latest else 100

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        discounts_data = validated_data.pop("discounts", [])
        service_type_key = validated_data.pop("service_type_key")
        branch = validated_data.pop("branch_id", None)
        if branch is None:
            branch = Branch.objects.first()
            if branch is None:
                raise serializers.ValidationError("Branch is required")

        service_type = ServiceType.objects.filter(key=service_type_key).first()
        if service_type is None:
            raise serializers.ValidationError("Service type is required")

        order_number = self._next_order_number(branch)
        order = Order.objects.create(
            branch=branch,
            order_number=order_number,
            service_type=service_type,
            **validated_data,
        )

        subtotal = Decimal("0")

        for item_data in items_data:
            modifiers = item_data.pop("modifiers", [])
            product = item_data.pop("product_id")
            price_snapshot = item_data["price_snapshot"]
            quantity = item_data["quantity"]
            modifiers_total = sum((modifier["price"] for modifier in modifiers), Decimal("0"))
            item_total = (price_snapshot + modifiers_total) * quantity
            subtotal += item_total

            order_item = OrderItem.objects.create(order=order, product=product, **item_data)
            for modifier_data in modifiers:
                OrderItemModifier.objects.create(
                    order_item=order_item,
                    modifier_name_snapshot=modifier_data["name"],
                    modifier_price_snapshot=modifier_data["price"],
                )

        for discount_data in discounts_data:
            AppliedDiscount.objects.create(
                order=order,
                discount=discount_data["discount_id"],
                name=discount_data["name"],
                amount=discount_data["amount"],
            )

        tax_config = TaxConfig.objects.filter(branch=branch, is_active=True).first()
        tax_rate = tax_config.rate if tax_config else Decimal("0")
        tax = (subtotal * tax_rate).quantize(Decimal("0.01"))
        total = subtotal + tax
        order.subtotal = subtotal
        order.tax = tax
        order.total = total
        order.save(update_fields=["subtotal", "tax", "total"])

        return order
