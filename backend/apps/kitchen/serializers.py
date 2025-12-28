from rest_framework import serializers
from apps.kitchen.models import KitchenOrderView
from apps.orders.serializers import OrderItemSerializer


class KitchenOrderSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(source="order.order_number", read_only=True)
    customer_name = serializers.CharField(source="order.customer_name", read_only=True)
    items = OrderItemSerializer(source="order.items", many=True, read_only=True)

    class Meta:
        model = KitchenOrderView
        fields = [
            "id",
            "order_number",
            "customer_name",
            "status",
            "prep_time_minutes",
            "service_type_id",
            "items",
        ]
