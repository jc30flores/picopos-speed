from django.db import models, transaction
from django.db.models import Case, IntegerField, Value, When
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ActivityCatalog, Branch, Customer, FeatureFlag, GeoDepartment, GeoMunicipality, ServiceType, TaxConfig
from apps.core.permissions import IsAuthenticatedAndActive
from apps.core.serializers import ActivityCatalogSerializer, BranchSerializer, ClientSerializer, CustomerSerializer, FeatureFlagSerializer, GeoDepartmentSerializer, GeoMunicipalitySerializer, ServiceTypeSerializer, TaxConfigSerializer


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


class CustomerListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        qs = Customer.objects.all().order_by("-is_default_consumer_final", "name")
        search = (self.request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(models.Q(name__icontains=search) | models.Q(num_documento__icontains=search))
        return qs


class CustomerDetailView(generics.RetrieveUpdateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticatedAndActive]


class DefaultConsumerFinalView(generics.RetrieveAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_object(self):
        customer = Customer.objects.filter(is_default_consumer_final=True).first()
        if customer:
            return customer
        return Customer.objects.create(name="CONSUMIDOR FINAL", is_default_consumer_final=True)


class ClientListCreateView(generics.ListCreateAPIView):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Customer.objects.filter(is_deleted=False).order_by("full_name", "id")
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                models.Q(full_name__icontains=q)
                | models.Q(company_name__icontains=q)
                | models.Q(dui__icontains=q)
                | models.Q(nit__icontains=q)
                | models.Q(nrc__icontains=q)
                | models.Q(telefono__icontains=q)
                | models.Q(correo__icontains=q)
            )
        ctype = (self.request.query_params.get("client_type") or "").strip().upper()
        if ctype:
            qs = qs.filter(client_type=ctype)
        is_cf = self.request.query_params.get("is_consumer_final")
        if is_cf in {"true", "1", "false", "0"}:
            qs = qs.filter(is_consumer_final=is_cf in {"true", "1"})
        return qs


class ClientDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        if instance.is_consumer_final:
            instance.is_consumer_final = False
        instance.save(update_fields=["is_deleted", "is_consumer_final", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClientDefaultConsumerFinalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client = Customer.objects.filter(is_deleted=False, is_consumer_final=True).first()
        if not client:
            client = Customer.objects.create(
                name="CONSUMIDOR FINAL",
                full_name="CONSUMIDOR FINAL",
                client_type="CF",
                dui="00000000-0",
                telefono="00000000",
                is_consumer_final=True,
            )
        return Response(ClientSerializer(client).data)


class ClientSetConsumerFinalView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk: int):
        client = Customer.objects.filter(pk=pk, is_deleted=False).first()
        if not client:
            return Response({"detail": "Cliente no encontrado"}, status=status.HTTP_404_NOT_FOUND)
        if client.client_type != "CF":
            return Response({"detail": "Solo clientes CF pueden ser consumidor final"}, status=status.HTTP_400_BAD_REQUEST)
        Customer.objects.filter(is_deleted=False, is_consumer_final=True).update(is_consumer_final=False)
        client.is_consumer_final = True
        client.save(update_fields=["is_consumer_final", "updated_at"])
        return Response(ClientSerializer(client).data)


class GeoDepartmentListView(generics.ListAPIView):
    serializer_class = GeoDepartmentSerializer
    permission_classes = [IsAuthenticated]
    queryset = GeoDepartment.objects.all().order_by("name")


class GeoMunicipalityListView(generics.ListAPIView):
    serializer_class = GeoMunicipalitySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = GeoMunicipality.objects.all().order_by("name")
        dept = (self.request.query_params.get("department_code") or "").strip()
        if dept:
            qs = qs.filter(department_code=dept)
        return qs


class ActivityCatalogListView(generics.ListAPIView):
    serializer_class = ActivityCatalogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = ActivityCatalog.objects.all().order_by("description")
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(models.Q(description__icontains=q) | models.Q(code__icontains=q))
        return qs
