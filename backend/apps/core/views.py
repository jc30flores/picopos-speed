from django.db.models import Case, IntegerField, Value, When
from rest_framework import generics
from apps.core.models import Branch, FeatureFlag, ServiceType, TaxConfig
from apps.core.permissions import IsAuthenticatedAndActive
from apps.core.serializers import BranchSerializer, FeatureFlagSerializer, ServiceTypeSerializer, TaxConfigSerializer


class ServiceTypeListView(generics.ListAPIView):
    queryset = ServiceType.objects.filter(is_active=True).order_by("label")
    serializer_class = ServiceTypeSerializer
    permission_classes = [IsAuthenticatedAndActive]


class ActiveTaxConfigView(generics.RetrieveAPIView):
    serializer_class = TaxConfigSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_object(self):
        return TaxConfig.objects.filter(is_active=True).order_by("-id").first()


class FeatureFlagListView(generics.ListAPIView):
    queryset = FeatureFlag.objects.all().order_by("key")
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticatedAndActive]


class FeatureFlagDetailView(generics.RetrieveUpdateAPIView):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticatedAndActive]


class BranchListView(generics.ListAPIView):
    queryset = Branch.objects.filter(is_active=True, code__in=["PRINCIPAL", "PLAZA_MONACO"]).annotate(
        sort_default=Case(
            When(code="PRINCIPAL", then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("sort_default", "name")
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticatedAndActive]
