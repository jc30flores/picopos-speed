from decimal import Decimal
import logging
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework import generics
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework import status
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer, OrderCreateSerializer
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
from apps.payments.models import Payment
from apps.dte.models import DTERecord


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
        order = serializer.save()
        output = OrderSerializer(order, context={"request": request}).data
        return Response(output, status=status.HTTP_201_CREATED)


class OrderDetailView(generics.RetrieveAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        output = OrderSerializer(order, context={"request": request}).data
        return Response(output, status=status.HTTP_201_CREATED)


class ActiveOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):
        queryset = (
            Order.objects.filter(status__in=["preparing", "ready"], requires_kitchen=True)
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
        queryset = Order.objects.filter(status__in=["preparing", "ready"], requires_kitchen=True).order_by("created_at")
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
            Order.objects.filter(status__in=["new", "preparing"], requires_kitchen=True)
            .prefetch_related("items__applied_modifiers")
            .order_by("created_at")
        )
        queryset, branch_id, service_type = _apply_common_filters(self.request, queryset)
        logger.info("[ORDERS] kitchen branch_id=%s service_type=%s statuses=%s count=%s", branch_id, service_type, "new,preparing", queryset.count())
        return queryset


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

    def get(self, request, *args, **kwargs):
        order = self.get_object()
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="receipt_order_{order.id}.pdf"'

        record = DTERecord.objects.filter(order=order).order_by("-id").first()
        lines = [
            "Pico de Gallo - Recibo de Venta",
            f"Orden: {order.order_number}",
            f"Sucursal: {order.branch.name}",
            f"Fecha: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "Items",
        ]
        for item in order.items.all().prefetch_related("applied_modifiers"):
            lines.append(f"- {item.quantity} x {item.product_name_snapshot}  ${item.price_snapshot}")
            for mod in item.applied_modifiers.all():
                lines.append(f"  Extra: {mod.modifier_name_snapshot}  ${mod.modifier_price_snapshot}")
        lines += [
            "",
            f"Desechables: ${order.disposable_total}",
            f"Subtotal: ${order.subtotal}",
            f"Total: ${order.total}",
            "",
            "Datos DTE",
            f"No. Control: {record.control_number if record else '-'}",
            f"Codigo generacion: {record.codigo_generacion if record else '-'}",
            f"Sello/UUID: {(record.sello_recepcion or record.hacienda_uuid) if record else '-'}",
            f"Estado DTE: {record.status if record else '-'}",
        ]

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas

            pdf = canvas.Canvas(response, pagesize=A4)
            y = 800
            for line in lines:
                pdf.drawString(40, y, line)
                y -= 14
                if y < 60:
                    pdf.showPage()
                    y = 800
            pdf.showPage()
            pdf.save()
            return response
        except Exception:
            content = "\n".join(lines).replace("(", "[").replace(")", "]")
            blob = (
                "%PDF-1.1\n"
                "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
                "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
                f"4 0 obj<</Length {len(content)+60}>>stream\n"
                f"BT /F1 10 Tf 40 800 Td ({content}) Tj ET\n"
                "endstream endobj\n"
                "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
                "trailer<</Size 6/Root 1 0 R>>\n%%EOF"
            )
            response.write(blob.encode("latin-1", errors="ignore"))
            return response
