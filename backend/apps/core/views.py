from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from pathlib import Path
from django.db.models import Case, IntegerField, Value, When
from PIL import Image, UnidentifiedImageError
import logging
from rest_framework import generics, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ActivityCatalog, Branch, Customer, DTEGlobalSettings, FeatureFlag, GeoDepartment, GeoMunicipality, ServiceType, SystemAppearanceSettings, TaxConfig, TicketSettings
from apps.core.feature_flags import get_pos_quick_sales_settings, set_pos_quick_sales_settings
from apps.core.permissions import IsAdmin, IsAuthenticatedAndActive, IsSuperAdmin, can_manage_features, can_view_dte, is_admin, is_superadmin, user_can_manage_feature_key, user_can_view_features
from apps.core.serializers import ActivityCatalogSerializer, BranchSerializer, ClientSerializer, CustomerSerializer, DTEGlobalSettingsSerializer, FeatureFlagSerializer, GeoDepartmentSerializer, GeoMunicipalitySerializer, ServiceTypeSerializer, SystemAppearanceSettingsSerializer, TaxConfigSerializer, build_color_tokens
from apps.dte.runtime import DISABLED_MESSAGE, get_dte_runtime_status


logger = logging.getLogger(__name__)


FEATURE_FLAG_DEFAULTS = {
    "module_pos_enabled": {
        "label": "POS",
        "description": "Mostrar u ocultar venta rápida/POS.",
        "default": True,
        "metadata": {"category": "Venta rápida / POS"},
    },
    "module_open_orders_enabled": {
        "label": "Pedidos clientes",
        "description": "Mostrar u ocultar pedidos abiertos y pendientes.",
        "default": True,
        "metadata": {"category": "Venta rápida / POS"},
    },
    "FF_KIOSK_ENABLED": {
        "label": "KIOSK",
        "description": "Mostrar u ocultar el módulo KIOSK para todos los usuarios.",
        "default": True,
    },
    "module_menu_discounts_enabled": {
        "label": "Menú & descuentos",
        "description": "Mostrar u ocultar gestión de menú y descuentos.",
        "default": True,
        "metadata": {"category": "Operación / Pantallas"},
    },
    "module_reports_enabled": {
        "label": "Reportes",
        "description": "Mostrar u ocultar reportes y registros.",
        "default": True,
        "metadata": {"category": "Reportes"},
    },
    "module_clients_enabled": {
        "label": "Clientes",
        "description": "Mostrar u ocultar la gestión de clientes.",
        "default": True,
        "metadata": {"category": "Clientes"},
    },
    "module_settings_enabled": {
        "label": "Configuración para administradores",
        "description": "Oculta Configuración a administradores; superadmin siempre mantiene acceso.",
        "default": True,
        "metadata": {"category": "Seguridad / Caja"},
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
    "table_map_enabled": {
        "label": "Mapa de mesas",
        "description": "Activa el modo restaurante con mapa de mesas, editor de salón y órdenes por mesa.",
        "default": False,
    },
    "pos_quick_sales_button": {
        "label": "Botón rápido de ventas en POS",
        "description": "Controla si el botón rápido del POS reimprime la última venta, muestra historial o se oculta.",
        "default": True,
        "metadata": {"mode": "last_sale", "history_scope": "current_shift", "history_window_minutes": 60},
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


ADMIN_FEATURE_SETTINGS_FIELDS = {
    "operation_mode",
    "default_pos_entry",
    "allow_table_merge",
    "allow_table_transfer",
    "allow_split_by_guest",
    "allow_split_by_item",
    "table_map_enabled",
    "inventory_stock_policy",
    "inventory_advanced_enabled",
    "pos_product_images_enabled",
    "cash_close_expected_totals_control_enabled",
    "cash_close_expected_totals_allowed_roles",
    "cash_close_expected_totals_visible_fields",
    "pos_quick_sales_button_mode",
    "pos_quick_sales_history_scope",
    "pos_quick_sales_history_window_minutes",
}


def _filter_feature_settings_payload_for_user(payload: dict, user) -> dict:
    if is_superadmin(user):
        return payload
    return {key: value for key, value in payload.items() if key in ADMIN_FEATURE_SETTINGS_FIELDS}


def get_feature_settings_payload(user=None) -> dict:
    _ensure_feature_settings_flags()
    flags = {item.key: item for item in FeatureFlag.objects.filter(key__in=FEATURE_FLAG_DEFAULTS.keys())}
    totals_flag = flags["FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED"]
    stock_policy_flag = flags["FF_INVENTORY_STOCK_POLICY"]
    metadata = totals_flag.metadata or {}
    stock_policy_metadata = stock_policy_flag.metadata or {}
    stock_policy = str(stock_policy_metadata.get("policy") or "allow").lower()
    if stock_policy not in {"allow", "warn", "block"}:
        stock_policy = "allow"
    quick_sales = get_pos_quick_sales_settings()
    table_flag = flags["table_map_enabled"]
    table_metadata = dict(table_flag.metadata or {})
    operation_mode = str(table_metadata.get("operation_mode") or ("both" if table_flag.is_enabled else "quick_pos")).strip().lower()
    if operation_mode not in {"quick_pos", "table_service", "both"}:
        operation_mode = "quick_pos"
    default_pos_entry = str(table_metadata.get("default_pos_entry") or ("table_map" if operation_mode == "table_service" else "quick_pos")).strip().lower()
    if operation_mode == "quick_pos" or default_pos_entry not in {"quick_pos", "table_map"}:
        default_pos_entry = "quick_pos"
    payload = {
        "pos_enabled": bool(flags["module_pos_enabled"].is_enabled),
        "open_orders_enabled": bool(flags["module_open_orders_enabled"].is_enabled),
        "kiosk_enabled": bool(flags["FF_KIOSK_ENABLED"].is_enabled),
        "customer_display_enabled": bool(flags["FF_CUSTOMER_DISPLAY_ENABLED"].is_enabled),
        "kitchen_display_enabled": bool(flags["FF_KITCHEN_DISPLAY_ENABLED"].is_enabled),
        "menu_discounts_enabled": bool(flags["module_menu_discounts_enabled"].is_enabled),
        "reports_enabled": bool(flags["module_reports_enabled"].is_enabled),
        "clients_enabled": bool(flags["module_clients_enabled"].is_enabled),
        "settings_enabled": bool(flags["module_settings_enabled"].is_enabled),
        "cash_close_expected_totals_control_enabled": bool(totals_flag.is_enabled),
        "cash_close_expected_totals_allowed_roles": list(metadata.get("allowed_roles") or []),
        "cash_close_expected_totals_visible_fields": list(metadata.get("visible_fields") or []),
        "inventory_stock_policy": stock_policy,
        "inventory_advanced_enabled": bool(flags["FF_INVENTORY"].is_enabled),
        "pos_product_images_enabled": bool(flags["pos_product_images_enabled"].is_enabled),
        "table_map_enabled": bool(table_flag.is_enabled and operation_mode != "quick_pos"),
        "operation_mode": operation_mode,
        "default_pos_entry": default_pos_entry,
        "allow_table_merge": bool(table_metadata.get("allow_table_merge", True)),
        "allow_table_transfer": bool(table_metadata.get("allow_table_transfer", True)),
        "allow_split_by_guest": bool(table_metadata.get("allow_split_by_guest", True)),
        "allow_split_by_item": bool(table_metadata.get("allow_split_by_item", True)),
        "pos_quick_sales_button_mode": quick_sales["mode"],
        "pos_quick_sales_history_scope": quick_sales["history_scope"],
        "pos_quick_sales_history_window_minutes": quick_sales["history_window_minutes"],
    }
    return _filter_feature_settings_payload_for_user(payload, user) if user is not None else payload


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
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        return FeatureFlag.objects.exclude(
            key__in=["module_dte_enabled", "module_whatsapp_enabled", "module_email_enabled"]
        ).order_by("key")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        dte_settings = DTEGlobalSettings.objects.filter(pk=1).first()
        dte_enabled = bool(dte_settings and dte_settings.hacienda_enabled)
        can_dte = can_view_dte(request.user)
        rows = list(response.data)
        rows.extend(
            [
                {"id": None, "key": "dte_enabled", "label": "DTE activo", "description": "", "is_enabled": dte_enabled, "enabled": dte_enabled, "metadata": {}},
                {"id": None, "key": "dte_visible", "label": "DTE visible", "description": "", "is_enabled": dte_enabled and can_dte, "enabled": dte_enabled and can_dte, "metadata": {}},
                {"id": None, "key": "can_view_dte", "label": "Puede ver DTE", "description": "", "is_enabled": can_dte, "enabled": can_dte, "metadata": {}},
                {"id": None, "key": "can_manage_dte", "label": "Puede administrar DTE", "description": "", "is_enabled": is_superadmin(request.user), "enabled": is_superadmin(request.user), "metadata": {}},
                {"id": None, "key": "can_send_dte", "label": "Puede enviar DTE", "description": "", "is_enabled": dte_enabled and can_dte, "enabled": dte_enabled and can_dte, "metadata": {}},
                {"id": None, "key": "hacienda_enabled", "label": "Hacienda activo", "description": "", "is_enabled": dte_enabled, "enabled": dte_enabled, "metadata": {}},
                {"id": None, "key": "fiscal_email_enabled", "label": "Correo fiscal", "description": "", "is_enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_email_enabled), "enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_email_enabled), "metadata": {}},
                {"id": None, "key": "fiscal_whatsapp_enabled", "label": "WhatsApp fiscal", "description": "", "is_enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_whatsapp_enabled), "enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_whatsapp_enabled), "metadata": {}},
                {"id": None, "key": "fiscal_pdf_enabled", "label": "PDF fiscal", "description": "", "is_enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_pdf_enabled), "enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_pdf_enabled), "metadata": {}},
                {"id": None, "key": "fiscal_json_enabled", "label": "JSON fiscal", "description": "", "is_enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_json_enabled), "enabled": bool(dte_enabled and dte_settings and dte_settings.fiscal_json_enabled), "metadata": {}},
            ]
        )
        response.data = rows
        return response


class FeatureFlagDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return FeatureFlag.objects.exclude(
            key__in=["module_dte_enabled", "module_whatsapp_enabled", "module_email_enabled"]
        )


class FeatureSettingsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        return [IsAuthenticatedAndActive()]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not user_can_view_features(request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permiso para administrar Funciones.")

    def get(self, request):
        role = getattr(getattr(request.user, "profile", None), "role", None)
        print_role = role or "unknown"
        logger.info(
            "FEATURE_FLAGS_READ user_id=%s role=%s allowed=true",
            getattr(request.user, "id", None),
            print_role,
        )
        return Response(get_feature_settings_payload(request.user))

    @transaction.atomic
    def patch(self, request):
        _ensure_feature_settings_flags()
        disallowed = sorted(str(field) for field in request.data.keys() if not user_can_manage_feature_key(request.user, str(field)))
        if disallowed:
            return Response(
                {
                    "detail": "No tienes permiso para modificar estas funciones.",
                    "fields": disallowed,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        mapping = {
            "pos_enabled": "module_pos_enabled",
            "open_orders_enabled": "module_open_orders_enabled",
            "kiosk_enabled": "FF_KIOSK_ENABLED",
            "customer_display_enabled": "FF_CUSTOMER_DISPLAY_ENABLED",
            "kitchen_display_enabled": "FF_KITCHEN_DISPLAY_ENABLED",
            "menu_discounts_enabled": "module_menu_discounts_enabled",
            "reports_enabled": "module_reports_enabled",
            "clients_enabled": "module_clients_enabled",
            "settings_enabled": "module_settings_enabled",
            "cash_close_expected_totals_control_enabled": "FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED",
            "inventory_advanced_enabled": "FF_INVENTORY",
            "pos_product_images_enabled": "pos_product_images_enabled",
            "table_map_enabled": "table_map_enabled",
        }
        for field, key in mapping.items():
            if field in request.data:
                previous = FeatureFlag.objects.get(key=key)
                next_value = bool(request.data.get(field))
                if previous.is_enabled != next_value:
                    FeatureFlag.objects.filter(key=key).update(is_enabled=next_value)
                    from apps.core.audit import log_audit
                    log_audit(request, "features.toggle", "FeatureFlag", key, {"field": field, "previous": previous.is_enabled, "new": next_value})

        totals_flag = FeatureFlag.objects.get(key="FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED")
        metadata = dict(totals_flag.metadata or {})
        if "cash_close_expected_totals_allowed_roles" in request.data:
            metadata["allowed_roles"] = [str(value) for value in (request.data.get("cash_close_expected_totals_allowed_roles") or [])]
        if "cash_close_expected_totals_visible_fields" in request.data:
            metadata["visible_fields"] = [str(value) for value in (request.data.get("cash_close_expected_totals_visible_fields") or [])]
        totals_flag.metadata = metadata
        totals_flag.save(update_fields=["metadata"])

        quick_sales_payload = {
            "mode": request.data.get("pos_quick_sales_button_mode") if "pos_quick_sales_button_mode" in request.data else None,
            "history_scope": request.data.get("pos_quick_sales_history_scope") if "pos_quick_sales_history_scope" in request.data else None,
            "history_window_minutes": request.data.get("pos_quick_sales_history_window_minutes") if "pos_quick_sales_history_window_minutes" in request.data else None,
        }
        if any(value is not None for value in quick_sales_payload.values()):
            try:
                set_pos_quick_sales_settings(**quick_sales_payload)
            except ValueError as exc:
                return Response({"pos_quick_sales_button": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if "inventory_stock_policy" in request.data:
            policy = str(request.data.get("inventory_stock_policy") or "allow").strip().lower()
            if policy not in {"allow", "warn", "block"}:
                return Response({"inventory_stock_policy": "Política inválida."}, status=status.HTTP_400_BAD_REQUEST)
            stock_flag = FeatureFlag.objects.get(key="FF_INVENTORY_STOCK_POLICY")
            stock_metadata = dict(stock_flag.metadata or {})
            stock_metadata["policy"] = policy
            stock_flag.metadata = stock_metadata
            stock_flag.save(update_fields=["metadata"])

        table_flag = FeatureFlag.objects.get(key="table_map_enabled")
        table_metadata = dict(table_flag.metadata or {})
        operation_fields = {
            "operation_mode",
            "default_pos_entry",
            "allow_table_merge",
            "allow_table_transfer",
            "allow_split_by_guest",
            "allow_split_by_item",
        }
        if any(field in request.data for field in operation_fields):
            operation_mode = str(request.data.get("operation_mode") or table_metadata.get("operation_mode") or "quick_pos").strip().lower()
            if operation_mode not in {"quick_pos", "table_service", "both"}:
                return Response({"operation_mode": "Modo de operación inválido."}, status=status.HTTP_400_BAD_REQUEST)
            default_pos_entry = str(request.data.get("default_pos_entry") or table_metadata.get("default_pos_entry") or ("table_map" if operation_mode == "table_service" else "quick_pos")).strip().lower()
            if operation_mode == "quick_pos":
                default_pos_entry = "quick_pos"
            elif default_pos_entry not in {"quick_pos", "table_map"}:
                return Response({"default_pos_entry": "Entrada inicial inválida."}, status=status.HTTP_400_BAD_REQUEST)
            table_metadata["operation_mode"] = operation_mode
            table_metadata["default_pos_entry"] = default_pos_entry
            for field in ["allow_table_merge", "allow_table_transfer", "allow_split_by_guest", "allow_split_by_item"]:
                if field in request.data:
                    table_metadata[field] = bool(request.data.get(field))
            table_flag.metadata = table_metadata
            table_flag.is_enabled = operation_mode != "quick_pos"
            table_flag.save(update_fields=["metadata", "is_enabled"])
        return Response(get_feature_settings_payload(request.user))




_ALLOWED_TICKET_LOGO_TYPES = {"image/png", "image/jpeg"}
_ALLOWED_TICKET_LOGO_EXTENSIONS = {".png", ".jpg", ".jpeg"}
_TICKET_LOGO_MAX_BYTES = 2 * 1024 * 1024


def _ticket_logo_payload(request, settings: TicketSettings) -> dict:
    if not settings.ticket_logo:
        return {"ticket_logo_url": None, "ticket_logo_name": None, "has_ticket_logo": False}
    try:
        logo_url = settings.ticket_logo.url
    except ValueError:
        logo_url = None
    return {
        "ticket_logo_url": logo_url,
        "ticket_logo_name": Path(settings.ticket_logo.name).name if settings.ticket_logo.name else None,
        "has_ticket_logo": bool(logo_url),
    }


class TicketSettingsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        settings, _ = TicketSettings.objects.get_or_create(pk=1)
        return Response(_ticket_logo_payload(request, settings))


class TicketLogoView(APIView):
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("logo")
        if not upload:
            return Response({"detail": "Selecciona una imagen para el logo."}, status=status.HTTP_400_BAD_REQUEST)
        content_type = (getattr(upload, "content_type", "") or "").lower()
        extension = Path(getattr(upload, "name", "")).suffix.lower()
        if content_type not in _ALLOWED_TICKET_LOGO_TYPES or extension not in _ALLOWED_TICKET_LOGO_EXTENSIONS:
            return Response({"detail": "Solo se permiten imágenes PNG o JPG."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > _TICKET_LOGO_MAX_BYTES:
            return Response({"detail": "El logo no puede superar 2 MB."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            Image.open(upload).verify()
            upload.seek(0)
        except (UnidentifiedImageError, OSError, ValueError):
            return Response({"detail": "No se pudo procesar la imagen."}, status=status.HTTP_400_BAD_REQUEST)
        settings, _ = TicketSettings.objects.get_or_create(pk=1)
        if settings.ticket_logo:
            settings.ticket_logo.delete(save=False)
        settings.ticket_logo = upload
        settings.save(update_fields=["ticket_logo", "updated_at"])
        return Response(_ticket_logo_payload(request, settings))

    def delete(self, request):
        settings, _ = TicketSettings.objects.get_or_create(pk=1)
        if settings.ticket_logo:
            settings.ticket_logo.delete(save=False)
            settings.ticket_logo = None
            settings.save(update_fields=["ticket_logo", "updated_at"])
        return Response(_ticket_logo_payload(request, settings))


class FeatureSettingsOptionsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not user_can_view_features(request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("No tienes permiso para administrar Funciones.")

    def get(self, request):
        from apps.users.models import UserProfile

        roles = []
        for code, label in UserProfile.ROLE_CHOICES:
            if code in {"admin", "superadmin"}:
                continue
            roles.append({"code": code, "label": label})
        return Response({"roles": roles, "cash_close_expected_total_fields": CASH_EXPECTED_FIELDS})


class AppearanceSettingsView(APIView):
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        settings, _ = SystemAppearanceSettings.objects.get_or_create(pk=1)
        return Response(SystemAppearanceSettingsSerializer(settings).data)

    @transaction.atomic
    def patch(self, request):
        if not is_admin(request.user):
            return Response({"detail": "Sin permisos para cambiar apariencia."}, status=status.HTTP_403_FORBIDDEN)
        settings, _ = SystemAppearanceSettings.objects.select_for_update().get_or_create(pk=1)
        if request.data.get("restore_default"):
            tokens = build_color_tokens(SystemAppearanceSettings.DEFAULT_PRIMARY)
        else:
            try:
                tokens = build_color_tokens(str(request.data.get("primary_color") or "").strip())
            except Exception as exc:
                detail = getattr(exc, "detail", None)
                if isinstance(detail, dict):
                    return Response(detail, status=status.HTTP_400_BAD_REQUEST)
                return Response(
                    {
                        "error": "invalid_color",
                        "message": "El color seleccionado no se pudo validar.",
                        "suggestions": ["#2563EB", "#0F766E", "#374151"],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        previous = settings.primary_color
        for field, value in tokens.items():
            setattr(settings, field, value)
        settings.updated_by = request.user
        settings.save()
        from apps.core.audit import log_audit
        log_audit(request, "appearance.update", "SystemAppearanceSettings", settings.id, {"previous": previous, "new": settings.primary_color})
        return Response(SystemAppearanceSettingsSerializer(settings).data)


class PublicAppearanceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        settings, _ = SystemAppearanceSettings.objects.get_or_create(pk=1)
        data = SystemAppearanceSettingsSerializer(settings).data
        return Response(
            {
                "app_display_name": "GastroPOSV",
                "primary_color": data["primary_color"],
                "color_primary": data["color_primary"],
                "color_primary_hover": data["color_primary_hover"],
                "color_primary_soft": data["color_primary_soft"],
                "color_primary_border": data["color_primary_border"],
                "color_primary_text": data["color_primary_text"],
                "color_primary_contrast": data["color_primary_contrast"],
                "theme_mode": data["theme_mode"],
                "palette": data["palette"],
                "css_variables": data["css_variables"],
            }
        )


def get_dte_settings() -> DTEGlobalSettings:
    settings, _ = DTEGlobalSettings.objects.get_or_create(pk=1)
    return settings


DTE_COUNTER_TYPES = ["CF_01", "CCF_03", "NC_05", "ND_06", "SE_14"]


def _get_primary_branch() -> Branch:
    branch = Branch.objects.filter(is_active=True).order_by("id").first()
    if branch:
        return branch
    return Branch.objects.create(name="Sucursal principal", code="PRINCIPAL", is_active=True)


def _get_branch_config(branch: Branch):
    from apps.dte.models import DTEBranchConfig

    config, _ = DTEBranchConfig.objects.get_or_create(branch=branch)
    return config


def _safe_str(data, key: str) -> str:
    return str((data or {}).get(key) or "").strip()


def _sync_dte_branch_config(config, issuer: dict, branch_payload: dict, branch: Branch) -> list[str]:
    changed = []
    mapping = {
        "emisor_nombre": _safe_str(issuer, "legal_name") or _safe_str(issuer, "nombre") or _safe_str(issuer, "razon_social"),
        "emisor_nombre_comercial": _safe_str(issuer, "commercial_name") or _safe_str(issuer, "nombre_comercial"),
        "emisor_nit": _safe_str(issuer, "nit"),
        "emisor_nrc": _safe_str(issuer, "nrc"),
        "cod_actividad": _safe_str(issuer, "activity_code") or _safe_str(issuer, "cod_actividad"),
        "desc_actividad": _safe_str(issuer, "activity_description") or _safe_str(issuer, "desc_actividad"),
        "tipo_establecimiento": _safe_str(branch_payload, "establishment_type") or _safe_str(issuer, "establishment_type") or _safe_str(issuer, "tipo_establecimiento"),
        "direccion_departamento": _safe_str(issuer, "department") or _safe_str(issuer, "departamento"),
        "direccion_municipio": _safe_str(issuer, "municipality") or _safe_str(issuer, "municipio"),
        "direccion_complemento": _safe_str(branch_payload, "branch_address") or _safe_str(issuer, "address") or _safe_str(issuer, "direccion"),
        "telefono": _safe_str(issuer, "phone") or _safe_str(issuer, "telefono"),
        "correo": _safe_str(issuer, "email") or _safe_str(issuer, "correo"),
        "cod_estable_mh": _safe_str(branch_payload, "establishment_code_mh") or _safe_str(branch_payload, "codEstableMH"),
        "cod_estable": _safe_str(branch_payload, "establishment_code") or _safe_str(branch_payload, "codEstable"),
        "cod_punto_venta_mh": _safe_str(branch_payload, "pos_code_mh") or _safe_str(branch_payload, "codPuntoVentaMH"),
        "cod_punto_venta": _safe_str(branch_payload, "pos_code") or _safe_str(branch_payload, "codPuntoVenta"),
    }
    for field, value in mapping.items():
        if value and getattr(config, field) != value:
            setattr(config, field, value)
            changed.append(field)
    branch_name = _safe_str(branch_payload, "name") or _safe_str(branch_payload, "branch_name")
    if branch_name and branch.name != branch_name:
        branch.name = branch_name
        branch.save(update_fields=["name"])
    branch_address = _safe_str(branch_payload, "address")
    if branch_address and branch.address != branch_address:
        branch.address = branch_address
        branch.save(update_fields=["address"])
    if changed:
        config.save(update_fields=[*changed, "updated_at"])
    return changed


def _initialize_correlatives(branch: Branch, settings: DTEGlobalSettings) -> int:
    from apps.dte.models import DTEControlCounter

    config = _get_branch_config(branch)
    est = (config.cod_estable or config.cod_estable_mh or "X001")[:4].upper()
    pos = (config.cod_punto_venta or config.cod_punto_venta_mh or "X001")[:4].upper()
    year = timezone.localdate().year
    created = 0
    for dte_type in DTE_COUNTER_TYPES:
        _row, was_created = DTEControlCounter.objects.get_or_create(
            branch=branch,
            ambiente=settings.ambiente,
            dte_type=dte_type,
            year=year,
            establishment_code=est,
            pos_code=pos,
            defaults={"last_number": 0},
        )
        created += int(was_created)
    return created


class DTEGlobalSettingsView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        settings = get_dte_settings()
        data = DTEGlobalSettingsSerializer(settings, context={"request": request}).data
        runtime = get_dte_runtime_status()
        data["can_manage_technical"] = is_superadmin(request.user)
        data["config_ready"] = runtime.config_ready
        data["message"] = runtime.message
        return Response(data)

    @transaction.atomic
    def patch(self, request):
        if not is_superadmin(request.user):
            return Response({"detail": "Solo superadmin puede cambiar configuración técnica DTE."}, status=status.HTTP_403_FORBIDDEN)
        settings = DTEGlobalSettings.objects.select_for_update().get_or_create(pk=1)[0]
        branch = _get_primary_branch()
        branch_config = _get_branch_config(branch)
        previous = {
            "hacienda_enabled": settings.hacienda_enabled,
            "ambiente": settings.ambiente,
            "base_url": settings.base_url,
            "api_token": "***" if settings.api_token else "",
            "timeout_seconds": settings.timeout_seconds,
            "retry_count": settings.retry_count,
            "fiscal_email_enabled": settings.fiscal_email_enabled,
            "fiscal_whatsapp_enabled": settings.fiscal_whatsapp_enabled,
            "fiscal_pdf_enabled": settings.fiscal_pdf_enabled,
            "fiscal_json_enabled": settings.fiscal_json_enabled,
        }
        if "hacienda_enabled" in request.data:
            settings.hacienda_enabled = bool(request.data.get("hacienda_enabled"))
        if "enabled" in request.data:
            settings.hacienda_enabled = bool(request.data.get("enabled"))
        if "ambiente" in request.data:
            ambiente = str(request.data.get("ambiente") or DTEGlobalSettings.AMBIENTE_TEST)
            if ambiente not in {DTEGlobalSettings.AMBIENTE_TEST, DTEGlobalSettings.AMBIENTE_PROD}:
                return Response({"ambiente": "Ambiente inválido."}, status=status.HTTP_400_BAD_REQUEST)
            settings.ambiente = ambiente
        if "environment" in request.data:
            environment = str(request.data.get("environment") or "test").strip().lower()
            if environment not in {"test", "production"}:
                return Response({"environment": "Ambiente inválido."}, status=status.HTTP_400_BAD_REQUEST)
            settings.ambiente = DTEGlobalSettings.AMBIENTE_PROD if environment == "production" else DTEGlobalSettings.AMBIENTE_TEST
        if "base_url" in request.data:
            settings.base_url = str(request.data.get("base_url") or "").strip()
        if "api_token" in request.data and str(request.data.get("api_token") or "").strip():
            settings.api_token = str(request.data.get("api_token")).strip()
        if request.data.get("clear_token"):
            settings.api_token = ""
        if "timeout_seconds" in request.data:
            settings.timeout_seconds = max(1, min(120, int(request.data.get("timeout_seconds") or 15)))
        if "retry_count" in request.data:
            settings.retry_count = max(0, min(10, int(request.data.get("retry_count") or 0)))
        api_payload = request.data.get("api") if isinstance(request.data.get("api"), dict) else {}
        if api_payload:
            if "base_url" in api_payload:
                settings.base_url = _safe_str(api_payload, "base_url")
            if "api_token" in api_payload and _safe_str(api_payload, "api_token"):
                settings.api_token = _safe_str(api_payload, "api_token")
            if api_payload.get("clear_token"):
                settings.api_token = ""
            if "timeout_seconds" in api_payload:
                settings.timeout_seconds = max(1, min(120, int(api_payload.get("timeout_seconds") or 15)))
            if "retry_count" in api_payload:
                settings.retry_count = max(0, min(10, int(api_payload.get("retry_count") or 0)))
        for field in ("fiscal_email_enabled", "fiscal_whatsapp_enabled", "fiscal_pdf_enabled", "fiscal_json_enabled"):
            if field in request.data:
                setattr(settings, field, bool(request.data.get(field)))
        issuer_payload = request.data.get("issuer") if isinstance(request.data.get("issuer"), dict) else {}
        branch_payload = request.data.get("branch") if isinstance(request.data.get("branch"), dict) else {}
        if issuer_payload or branch_payload:
            _sync_dte_branch_config(branch_config, issuer_payload, branch_payload, branch)
        if request.data.get("initialize_correlatives"):
            _initialize_correlatives(branch, settings)
        if not settings.hacienda_enabled:
            settings.status = DTEGlobalSettings.STATUS_DISABLED
        elif not settings.base_url or not settings.api_token or DTEGlobalSettingsSerializer(settings, context={"request": request}).get_pending_fields(settings):
            settings.status = DTEGlobalSettings.STATUS_PENDING
        else:
            settings.status = DTEGlobalSettings.STATUS_CONFIGURED
        settings.updated_by = request.user
        settings.save()
        from apps.core.audit import log_audit
        log_audit(
            request,
            "dte.settings.update",
            "DTEGlobalSettings",
            settings.id,
            {"previous": previous, "new": {**previous, "hacienda_enabled": settings.hacienda_enabled, "ambiente": settings.ambiente, "base_url": settings.base_url, "api_token": "***" if settings.api_token else ""}},
        )
        runtime = get_dte_runtime_status()
        data = DTEGlobalSettingsSerializer(settings, context={"request": request}).data
        data["can_manage_technical"] = is_superadmin(request.user)
        data["config_ready"] = runtime.config_ready
        data["message"] = runtime.message
        return Response(data)


class DTECorrelativesView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        settings = get_dte_settings()
        data = DTEGlobalSettingsSerializer(settings, context={"request": request}).data
        return Response({"correlatives": data["correlatives"], "permissions": data["permissions"]})

    @transaction.atomic
    def post(self, request):
        if not is_superadmin(request.user):
            return Response({"detail": "Solo superadmin puede inicializar correlativos."}, status=status.HTTP_403_FORBIDDEN)
        settings = get_dte_settings()
        created = _initialize_correlatives(_get_primary_branch(), settings)
        from apps.core.audit import log_audit

        log_audit(request, "dte.correlatives.initialize", "DTEControlCounter", "bulk", {"created": created})
        data = DTEGlobalSettingsSerializer(settings, context={"request": request}).data
        return Response({"created": created, "correlatives": data["correlatives"]})


class DTECorrelativeDetailView(APIView):
    permission_classes = [IsSuperAdmin]

    @transaction.atomic
    def patch(self, request, pk: int):
        from apps.dte.models import DTEControlCounter, DTERecord

        reason = _safe_str(request.data, "reason") or _safe_str(request.data, "motivo")
        if not reason:
            return Response({"reason": "El motivo es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            next_last = int(request.data.get("last_number"))
        except (TypeError, ValueError):
            return Response({"last_number": "Número inválido."}, status=status.HTTP_400_BAD_REQUEST)
        counter = get_object_or_404(DTEControlCounter.objects.select_for_update(), pk=pk)
        if next_last < counter.last_number and not request.data.get("confirm_decrease"):
            return Response(
                {
                    "error": "decrease_requires_confirmation",
                    "message": "Cambiar correlativos hacia abajo puede duplicar numeración fiscal. Confirma explícitamente para continuar.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        prefix = f"DTE-{counter.dte_type.split('_')[-1]}-{counter.establishment_code}{counter.pos_code}-"
        if DTERecord.objects.filter(control_number__startswith=prefix, control_number__endswith=f"{next_last:015d}").exists():
            return Response({"last_number": "Ya existe un DTE con ese número de control."}, status=status.HTTP_400_BAD_REQUEST)
        previous = counter.last_number
        counter.last_number = next_last
        counter.save(update_fields=["last_number", "updated_at"])
        from apps.core.audit import log_audit

        log_audit(request, "dte.correlative.update", "DTEControlCounter", counter.id, {"previous": previous, "new": next_last, "reason": reason})
        settings = get_dte_settings()
        data = DTEGlobalSettingsSerializer(settings, context={"request": request}).data
        return Response({"correlative": next((row for row in data["correlatives"] if row["id"] == counter.id), None), "correlatives": data["correlatives"]})


class DTETestConnectionView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        settings = get_dte_settings()
        missing = DTEGlobalSettingsSerializer(settings, context={"request": request}).get_pending_fields(settings)
        if missing:
            return Response({"ok": False, "status": "pending", "missing": missing, "message": "Configuración incompleta. No se contactó Hacienda."}, status=status.HTTP_200_OK)
        return Response({"ok": True, "status": "configured", "message": "Configuración mínima completa. Prueba externa no ejecutada desde este entorno."})


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
