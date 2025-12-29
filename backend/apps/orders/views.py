from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer, OrderCreateSerializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from apps.core.audit import log_audit
from apps.core.permissions import (
    IsAuthenticatedAndActive,
    IsCashierOrManagerOrAdmin,
    IsKitchenOrManagerOrAdmin,
)


class CustomerDisplayOrderSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField(source="order_number")
    customer_name = serializers.CharField(source="customer_name")

    class Meta:
        model = Order
        fields = ["id", "order_number", "customer_name", "status", "created_at"]


class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderCreateSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        output = OrderSerializer(order, context={"request": request}).data
        return Response(output, status=status.HTTP_201_CREATED)


class ActiveOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return (
            Order.objects.filter(status__in=["new", "preparing", "ready"])
            .prefetch_related("items__applied_modifiers")
            .order_by("created_at")
        )


class OrderStatusUpdateView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    http_method_names = ["patch"]
    permission_classes = [IsKitchenOrManagerOrAdmin]

    def patch(self, request, *args, **kwargs):
        order = self.get_object()
        status_value = request.data.get("status")
        if status_value:
            order.status = status_value
            order.save(update_fields=["status", "updated_at"])
            log_audit(
                request,
                "order.status.update",
                "Order",
                order.id,
                {"status": order.status},
            )
        data = OrderSerializer(order, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)


class CustomerDisplayOrderListView(generics.ListAPIView):
    serializer_class = CustomerDisplayOrderSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Order.objects.filter(status__in=["new", "preparing", "ready"]).order_by("created_at")
