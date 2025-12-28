from rest_framework import generics
from apps.core.models import ServiceType
from apps.core.serializers import ServiceTypeSerializer


class ServiceTypeListView(generics.ListAPIView):
    queryset = ServiceType.objects.filter(is_active=True).order_by("label")
    serializer_class = ServiceTypeSerializer
