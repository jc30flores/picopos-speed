from decimal import Decimal
import logging
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from rest_framework import generics
from rest_framework.views import APIView
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework import status
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer, OrderCreateSerializer, OrderCustomerUpdateSerializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from apps.core.audit import log_audit
from apps.core.permissions import (
    IsAuthenticatedAndActive,
    IsCashierOrManagerOrAdmin,
    IsKitchenOrManagerOrAdmin,
    IsAdminOrManager,
)
from apps.printing.models import PrintJob
from apps.printing.services.jobs import create_print_job, create_void_print_job
from apps.printing.services.renderers import render_customer_ticket
from apps.payments.models import Payment
from apps.cashier.models import CashSession, Register
from apps.printing.receipt_pdf import build_receipt_pdf_from_text
from apps.users.models import UserProfile
from apps.users.pin_utils import is_valid_pin_format, user_matches_pin


logger = logging.getLogger(__name__)


def _selected_branch_id(request):
    raw = request.query_params.get("branch_id")
    if raw and str(raw).isdigit():
        return int(raw)
    from apps.core.models import Branch

    principal = Branch.objects.filter(code="PRINCIPAL", is_active=True).first()
    if principal:
        return principal.id
    first = Branch.objects.filter(is_active=True).order_by("id").first()
    return first.id if first else None


def _apply_common_filters(request, queryset):
    branch_id = _selected_branch_id(request)
    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)
    service_type = (request.query_params.get("service_type") or request.query_params.get("service_type_key") or "all").strip().lower()
    if service_type and service_type not in {"all", "todos"}:
        queryset = queryset.filter(service_type__key=service_type)
    return queryset, branch_id, service_type


def _has_open_cash_session(branch_id: int | None) -> bool:
    if not branch_id:
        return False
    if not Register.objects.filter(branch_id=branch_id, is_active=True).exists():
        return True
    return CashSession.objects.filter(register__branch_id=branch_id, status="open", closed_at__isnull=True).exists()


class CustomerDisplayOrderSerializer(serializers.ModelSerializer):
    order_number = serializers.IntegerField()
    customer_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Order
        fields = ["id", "order_number", "customer_name", "status", "created_at"]


class OrderCreateView(generics.CreateAPIView):
    serializer_class = OrderCreateSerializer

    def get_permissions(self):
        source = ""
        if hasattr(self.request, "data"):
            source = str(self.request.data.get("source", "")).strip().lower()
        if source == "kiosk":
            return [AllowAny()]
        return [IsCashierOrManagerOrAdmin()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = str(serializer.validated_data.get("source") or "").strip().lower()
        branch = serializer.validated_data.get("branch_id")
        branch_id = getattr(branch, "id", None)
        if source != "kiosk" and not _has_open_cash_session(branch_id):
            return Response(
                {"code": "CASH_SESSION_REQUIRED", "detail": "Caja no aperturada."},
                status=status.HTTP_409_CONFLICT,
            )
        order = serializer.save()
        output = OrderSerializer(order, context={"request": request}).data
        return Response(output, status=status.HTTP_201_CREATED)


class ValidatePricePinView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, *args, **kwargs):
        pin = str(request.data.get("pin", "") or "").strip()
        if not is_valid_pin_format(pin):
            return Response({"detail": "Código inválido"}, status=status.HTTP_401_UNAUTHORIZED)

        privileged_profiles = UserProfile.objects.select_related("user").filter(
            is_active=True,
            role__in=["admin", "manager"],
            user__is_active=True,
        )
        for profile in privileged_profiles:
            if profile.user and user_matches_pin(profile.user, pin):
                return Response(status=status.HTTP_204_NO_CONTENT)

        logger.warning("orders.validate_price_pin.failed user_id=%s", getattr(request.user, "id", None))
        return Response({"detail": "Código inválido"}, status=status.HTTP_401_UNAUTHORIZED)


class OrderDetailView(generics.RetrieveUpdateAPIView):
    queryset = Order.objects.all()
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return OrderCustomerUpdateSerializer
        return OrderSerializer

    def patch(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        order = serializer.instance
        output = OrderSerializer(order, context={"request": request}).data
        log_audit(
            request,
            "order.customer.update",
            "Order",
            order.id,
            {"customer_id": order.customer_id, "dte_document_type": order.dte_document_type},
        )
        return Response(output, status=status.HTTP_200_OK)


class ActiveOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        queryset = (
            Order.objects.filter(status__in=["preparing", "ready"], requires_kitchen=True, send_to_kitchen=True)
            .prefetch_related("items__applied_modifiers")
            .order_by("created_at")
        )
        queryset, branch_id, service_type = _apply_common_filters(self.request, queryset)
        logger.info("[ORDERS] kitchen branch_id=%s service_type=%s statuses=%s count=%s", branch_id, service_type, "preparing,ready", queryset.count())
        return queryset


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
            if status_value == "preparing":
                exists = PrintJob.objects.filter(order=order, type="kitchen", meta__event="status.preparing").exists()
                if not exists:
                    create_print_job(order, "kitchen", requested_by=request.user, event="status.preparing")
        data = OrderSerializer(order, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)


class CustomerDisplayOrderListView(generics.ListAPIView):
    serializer_class = CustomerDisplayOrderSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Order.objects.filter(status__in=["preparing", "ready"], requires_kitchen=True, send_to_kitchen=True).order_by("created_at")
        queryset, branch_id, service_type = _apply_common_filters(self.request, queryset)
        logger.info("[ORDERS] customer-display branch_id=%s service_type=%s statuses=%s count=%s", branch_id, service_type, "preparing,ready", queryset.count())
        return queryset


class CustomerBoardListView(generics.ListAPIView):
    serializer_class = CustomerDisplayOrderSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        queryset = (
            Order.objects.filter(status__in=["preparing", "ready"])
            .only("id", "order_number", "customer_name", "status", "created_at")
            .order_by("created_at", "id")
        )
        queryset, branch_id, service_type = _apply_common_filters(self.request, queryset)
        logger.info("[ORDERS] customer-board branch_id=%s service_type=%s statuses=%s count=%s", branch_id, service_type, "preparing,ready", queryset.count())
        return queryset


class KitchenOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        queryset = (
            Order.objects.filter(status__in=["new", "preparing"], requires_kitchen=True, send_to_kitchen=True)
            .prefetch_related("items__applied_modifiers")
            .order_by("created_at")
        )
        queryset, branch_id, service_type = _apply_common_filters(self.request, queryset)
        logger.info("[ORDERS] kitchen branch_id=%s service_type=%s statuses=%s count=%s", branch_id, service_type, "new,preparing", queryset.count())
        return queryset


class OrderSendToKitchenView(generics.UpdateAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    http_method_names = ["patch"]
    permission_classes = [IsCashierOrManagerOrAdmin]

    def patch(self, request, *args, **kwargs):
        order = self.get_object()
        requested_value = bool(request.data.get("send_to_kitchen", False))
        should_enable = bool(requested_value and order.requires_kitchen)
        order.send_to_kitchen = should_enable
        if should_enable and order.payment_status == "paid":
            if order.status != "preparing":
                order.status = "preparing"
            from apps.kitchen.models import KitchenOrderView
            KitchenOrderView.objects.get_or_create(
                order=order,
                defaults={"service_type": order.service_type, "status": "preparing"},
            )
            order.save(update_fields=["send_to_kitchen", "status", "updated_at"])
        else:
            order.save(update_fields=["send_to_kitchen", "updated_at"])
        data = OrderSerializer(order, context={"request": request}).data
        return Response(data, status=status.HTTP_200_OK)


class OrderVoidView(generics.GenericAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAdminOrManager]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        order = self.get_object()
        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response({"detail": "Reason is required"}, status=status.HTTP_400_BAD_REQUEST)

        total_paid = Payment.objects.filter(order=order).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0")
        if total_paid > 0:
            return Response(
                {"detail": "Order has payments. Use refund instead."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = "canceled"
        order.payment_status = "unpaid"
        order.financial_status = "voided"
        order.refund_total = Decimal("0")
        order.net_paid = Decimal("0")
        order.save(
            update_fields=[
                "status",
                "payment_status",
                "financial_status",
                "refund_total",
                "net_paid",
                "updated_at",
            ]
        )
        log_audit(
            request,
            "order.void",
            "Order",
            order.id,
            {"order_id": order.id, "reason": reason},
        )
        job = create_void_print_job(order, reason, requested_by=request.user)
        data = OrderSerializer(order, context={"request": request}).data
        return Response({"order": data, "print_job_id": job.id}, status=status.HTTP_200_OK)


class OrderReceiptPDFView(generics.GenericAPIView):
    queryset = Order.objects.all()
    permission_classes = [IsAuthenticatedAndActive]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request, *args, **kwargs):
        order = self.get_object()
        payload = render_customer_ticket(order)
        filename = f"venta_{order.order_number}_{timezone.localtime(timezone.now()).strftime('%Y-%m-%d_%H-%M')}.pdf"
        result = build_receipt_pdf_from_text(
            text=payload.get("text", ""),
            filename=filename,
            logo_path=payload.get("meta", {}).get("logo_path"),
            qr_value=payload.get("meta", {}).get("public_url"),
            receipt_context=payload.get("meta", {}).get("receipt_context"),
            suppress_qr_url_lines=True,
        )
        response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
        return response
