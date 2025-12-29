from rest_framework import generics
from apps.core.models import ServiceType, TaxConfig
from apps.core.serializers import ServiceTypeSerializer, TaxConfigSerializer


class ServiceTypeListView(generics.ListAPIView):
    queryset = ServiceType.objects.filter(is_active=True).order_by("label")
    serializer_class = ServiceTypeSerializer


class ActiveTaxConfigView(generics.RetrieveAPIView):
    serializer_class = TaxConfigSerializer

    def get_object(self):
        return TaxConfig.objects.filter(is_active=True).order_by("-id").first()
