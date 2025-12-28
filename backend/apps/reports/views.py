from rest_framework import generics
from apps.reports.models import SaleSnapshot
from apps.reports.serializers import SaleSnapshotSerializer


class SaleSnapshotListView(generics.ListAPIView):
    queryset = SaleSnapshot.objects.select_related("branch", "service_type").all()
    serializer_class = SaleSnapshotSerializer
