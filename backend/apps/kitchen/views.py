from rest_framework import generics
from apps.kitchen.models import KitchenOrderView
from apps.kitchen.serializers import KitchenOrderSerializer


class KitchenOrderListView(generics.ListAPIView):
    serializer_class = KitchenOrderSerializer

    def get_queryset(self):
        return KitchenOrderView.objects.select_related("order", "service_type").prefetch_related("order__items")
