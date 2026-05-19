from django.db import models, transaction
from django.db.models import Case, IntegerField, Value, When
import logging
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ActivityCatalog, Branch, Customer, FeatureFlag, GeoDepartment, GeoMunicipality, ServiceType, TaxConfig
from apps.core.permissions import IsAdmin, IsAuthenticatedAndActive
from apps.core.serializers import ActivityCatalogSerializer, BranchSerializer, ClientSerializer, CustomerSerializer, FeatureFlagSerializer, GeoDepartmentSerializer, GeoMunicipalitySerializer, ServiceTypeSerializer, TaxConfigSerializer


logger = logging.getLogger(__name__)


FEATURE_FLAG_DEFAULTS = {
    "FF_KIOSK_ENABLED": {
        "label": "KIOSK",
        "description": "Mostrar u ocultar el módulo KIOSK para todos los usuarios.",
        "default": True,
    },
    "FF_CUSTOMER_DISPLAY_ENABLED": {
        "label": "Pantalla Cliente",
        "description": "Mostrar u ocultar la pantalla cliente para todos los usuarios.",
        "default": True,
    },
    "FF_KITCHEN_DISPLAY_ENABLED": {
        "label": "Pantalla Cocina",
        "description": "Mostrar u ocultar Cocina para todos los usuarios.",
        "default": True,
    },
    "FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED": {
        "label": "Totales esperados en cierre de caja",
        "description": "Controlar visibilidad de totales esperados en cierre de caja.",
        "default": True,
    },
    "FF_INVENTORY": {
        "label": "Inventario avanzado",
        "description": "Activa proveedores, costos y órdenes de compra dentro del inventario.",
        "default": False,
    },
    "FF_INVENTORY_STOCK_POLICY": {
        "label": "Política de stock insuficiente",
        "description": "Define cómo debe comportarse el POS cuando una venta necesita más inventario del disponible.",
        "default": True,
        "metadata": {"policy": "allow"},
    },
    "pos_product_images_enabled": {
        "label": "Imágenes de productos en POS",
        "description": "Muestra las imágenes guardadas de los productos en las tarjetas del POS.",
        "default": False,
    },
}

CASH_EXPECTED_FIELDS = [
    {"code": "expected_cash_in_drawer", "label": "Efectivo esperado"},
    {"code": "card_expected", "label": "Tarjeta esperado"},
    {"code": "pedidos_ya_expected", "label": "Pedidos Ya esperado"},
    {"code": "transfer_expected", "label": "Transferencia esperado"},
    {"code": "paypal_expected", "label": "PayPal esperado"},
    {"code": "total_expected", "label": "Total esperado general"},
    {"code": "difference", "label": "Diferencias"},
]


def _ensure_feature_settings_flags():
    for key, config in FEATURE_FLAG_DEFAULTS.items():
        FeatureFlag.objects.get_or_create(
            key=key,
            defaults={
                "label": config["label"],
                "description": config["description"],
                "is_enabled": bool(config["default"]),
                "metadata": dict(config.get("metadata") or {}),
            },
        )


def get_feature_settings_payload() -> dict:
    _ensure_feature_settings_flags()
    flags = {item.key: item for item in FeatureFlag.objects.filter(key__in=FEATURE_FLAG_DEFAULTS.keys())}
    totals_flag = flags["FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED"]
    stock_policy_flag = flags["FF_INVENTORY_STOCK_POLICY"]
    metadata = totals_flag.metadata or {}
    stock_policy_metadata = stock_policy_flag.metadata or {}
    stock_policy = str(stock_policy_metadata.get("policy") or "allow").lower()
    if stock_policy not in {"allow", "warn", "block"}:
        stock_policy = "allow"
    return {
        "kiosk_enabled": bool(flags["FF_KIOSK_ENABLED"].is_enabled),
        "customer_display_enabled": bool(flags["FF_CUSTOMER_DISPLAY_ENABLED"].is_enabled),
        "kitchen_display_enabled": bool(flags["FF_KITCHEN_DISPLAY_ENABLED"].is_enabled),
        "cash_close_expected_totals_control_enabled": bool(totals_flag.is_enabled),
        "cash_close_expected_totals_allowed_roles": list(metadata.get("allowed_roles") or []),
        "cash_close_expected_totals_visible_fields": list(metadata.get("visible_fields") or []),
        "inventory_stock_policy": stock_policy,
        "inventory_advanced_enabled": bool(flags["FF_INVENTORY"].is_enabled),
        "pos_product_images_enabled": bool(flags["pos_product_images_enabled"].is_enabled),
    }


class ServiceTypeListView(generics.ListAPIView):
    queryset = ServiceType.objects.filter(is_active=True).order_by("sort_order", "label")
    serializer_class = ServiceTypeSerializer
    permission_classes = [IsAuthenticatedAndActive]


class ServiceTypeAdminListCreateView(generics.ListCreateAPIView):
    queryset = ServiceType.objects.all().order_by("sort_order", "label")
    serializer_class = ServiceTypeSerializer
    permission_classes = [IsAuthenticatedAndActive]


class ServiceTypeAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ServiceType.objects.all()
    serializer_class = ServiceTypeSerializer
    permission_classes = [IsAuthenticatedAndActive]

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        from apps.orders.models import Order
        from apps.kitchen.models import KitchenOrderView
        from apps.reports.models import SaleSnapshot

        Order.objects.filter(service_type=instance).update(service_type=None)
        KitchenOrderView.objects.filter(service_type=instance).update(service_type=None)
        SaleSnapshot.objects.filter(service_type=instance).update(service_type=None)

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


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


class FeatureSettingsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            return [IsAuthenticatedAndActive()]
        role = getattr(getattr(self.request.user, "profile", None), "role", None)
        if role != "admin" and not getattr(self.request.user, "is_superuser", False):
            logger.warning(
                "FEATURE_FLAGS_WRITE_DENIED user_id=%s role=%s",
                getattr(self.request.user, "id", None),
                role or "unknown",
            )
        return [IsAdmin()]

    def get(self, request):
        role = getattr(getattr(request.user, "profile", None), "role", None)
        print_role = role or "unknown"
        logger.info(
            "FEATURE_FLAGS_READ user_id=%s role=%s allowed=true",
            getattr(request.user, "id", None),
            print_role,
        )
        return Response(get_feature_settings_payload())

    @transaction.atomic
    def patch(self, request):
        _ensure_feature_settings_flags()
        mapping = {
            "kiosk_enabled": "FF_KIOSK_ENABLED",
            "customer_display_enabled": "FF_CUSTOMER_DISPLAY_ENABLED",
            "kitchen_display_enabled": "FF_KITCHEN_DISPLAY_ENABLED",
            "cash_close_expected_totals_control_enabled": "FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED",
            "inventory_advanced_enabled": "FF_INVENTORY",
            "pos_product_images_enabled": "pos_product_images_enabled",
        }
        for field, key in mapping.items():
            if field in request.data:
                FeatureFlag.objects.filter(key=key).update(is_enabled=bool(request.data.get(field)))

        totals_flag = FeatureFlag.objects.get(key="FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED")
        metadata = dict(totals_flag.metadata or {})
        if "cash_close_expected_totals_allowed_roles" in request.data:
            metadata["allowed_roles"] = [str(value) for value in (request.data.get("cash_close_expected_totals_allowed_roles") or [])]
        if "cash_close_expected_totals_visible_fields" in request.data:
            metadata["visible_fields"] = [str(value) for value in (request.data.get("cash_close_expected_totals_visible_fields") or [])]
        totals_flag.metadata = metadata
        totals_flag.save(update_fields=["metadata"])

        if "inventory_stock_policy" in request.data:
            policy = str(request.data.get("inventory_stock_policy") or "allow").strip().lower()
            if policy not in {"allow", "warn", "block"}:
                return Response({"inventory_stock_policy": "Política inválida."}, status=status.HTTP_400_BAD_REQUEST)
            stock_flag = FeatureFlag.objects.get(key="FF_INVENTORY_STOCK_POLICY")
            stock_metadata = dict(stock_flag.metadata or {})
            stock_metadata["policy"] = policy
            stock_flag.metadata = stock_metadata
            stock_flag.save(update_fields=["metadata"])
        return Response(get_feature_settings_payload())


class FeatureSettingsOptionsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        from apps.users.models import UserProfile

        roles = []
        for code, label in UserProfile.ROLE_CHOICES:
            if code == "admin":
                continue
            roles.append({"code": code, "label": label})
        return Response({"roles": roles, "cash_close_expected_total_fields": CASH_EXPECTED_FIELDS})


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
