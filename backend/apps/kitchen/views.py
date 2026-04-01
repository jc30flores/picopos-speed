from rest_framework import generics
from apps.kitchen.models import KitchenOrderView
from apps.kitchen.serializers import KitchenOrderSerializer
from apps.core.permissions import IsKitchenOrAdmin


class KitchenOrderListView(generics.ListAPIView):
    serializer_class = KitchenOrderSerializer
    permission_classes = [IsKitchenOrAdmin]

    def get_queryset(self):
        return (
            KitchenOrderView.objects.filter(status="preparing")
            .select_related("order", "service_type")
            .prefetch_related("order__items")
        )
