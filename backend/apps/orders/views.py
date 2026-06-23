from decimal import Decimal, ROUND_HALF_UP
import logging
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils import timezone
from rest_framework import generics
from rest_framework.views import APIView
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework import status
from apps.orders.models import AppliedDiscount, Order, OrderFee, OrderItem, OrderItemModifier
from apps.menu.models import Modifier, Product
from apps.orders.serializers import OrderSerializer, OrderCreateSerializer, OrderCustomerUpdateSerializer
from apps.orders.schema import ensure_whatsapp_order_columns, has_whatsapp_order_columns
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
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
from apps.cashier.services import has_open_cash_session_for_branch, resolve_branch_id
from apps.printing.receipt_pdf import build_receipt_pdf_from_text
from apps.users.models import UserProfile
from apps.users.pin_utils import is_valid_pin_format, user_matches_pin


logger = logging.getLogger(__name__)


def _selected_branch_id(request):
    raw = request.query_params.get("branch_id")
    return resolve_branch_id(raw, fallback_to_default=True)


def _selected_branch_id_optional(request):
    raw = (
        request.query_params.get("branch_id")
        or request.headers.get("X-Branch-Id")
        or request.headers.get("x-branch-id")
    )
    return resolve_branch_id(raw, fallback_to_default=False)


def _apply_common_filters(request, queryset):
    branch_id = _selected_branch_id(request)
    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)
    service_type = (request.query_params.get("service_type") or request.query_params.get("service_type_key") or "all").strip().lower()
    if service_type and service_type not in {"all", "todos"}:
        queryset = queryset.filter(service_type__key=service_type)
    return queryset, branch_id, service_type


def _require_manager_pin_for_cashier(request, pin: str) -> bool:
    profile = UserProfile.objects.filter(user=request.user, is_active=True).first()
    if getattr(request.user, "is_superuser", False) or (profile and profile.role in {"admin", "manager"}):
        return True
    if not profile or profile.role != "cashier":
        return False
    if not is_valid_pin_format(pin):
        return False
    privileged_profiles = UserProfile.objects.select_related("user").filter(
        is_active=True,
        role__in=["admin", "manager"],
        user__is_active=True,
    )
    return any(user_matches_pin(p.user, pin) for p in privileged_profiles)


def _is_privileged_user(user) -> bool:
    profile = UserProfile.objects.filter(user=user, is_active=True).first()
    return bool(getattr(user, "is_superuser", False) or (profile and profile.role in {"admin", "manager"}))


def _to_money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _sync_pending_order_lines(order: Order, items_data: list[dict], request, authorization_pin: str) -> None:
    previous_total = _to_money(order.total or 0)
    logger.info(
        "open_order.update.before_totals order_id=%s subtotal=%s discounts=%s fees=%s total=%s items=%s",
        order.id,
        order.subtotal,
        order.discount_total,
        order.disposable_total,
        order.total,
        len(items_data),
    )
    existing_ids = set(order.items.values_list("id", flat=True))
    requested_ids = {
        int(str(item.get("source_order_item_id")))
        for item in items_data
        if str(item.get("source_order_item_id") or "").isdigit()
    }
    removed_ids = existing_ids - requested_ids if requested_ids else set()
    if removed_ids:
        if order.send_to_kitchen or order.status in {"preparing", "ready", "delivered"}:
            raise PermissionDenied("No se pueden eliminar productos: la orden ya fue enviada a cocina.")
        if not _is_privileged_user(request.user) and not _require_manager_pin_for_cashier(request, authorization_pin):
            raise PermissionDenied("Autorización de gerente/admin requerida para eliminar productos.")

    AppliedDiscount.objects.filter(order=order).delete()
    OrderFee.objects.filter(order=order).delete()
    order.items.all().delete()

    subtotal = Decimal("0.00")
    requires_kitchen = False
    for idx, raw in enumerate(items_data, start=1):
        product_id = raw.get("product_id")
        product = Product.objects.filter(id=product_id).first() if product_id else None
        quantity = int(raw.get("quantity") or 1)
        quantity = max(1, quantity)
        base_price = _to_money(raw.get("price_snapshot") or raw.get("unit_price_override") or raw.get("price") or 0)
        override = raw.get("unit_price_override")
        override_decimal = _to_money(override) if override is not None else None
        is_custom = bool(raw.get("is_custom"))
        product_name = str(raw.get("product_name_snapshot") or raw.get("product_name") or (product.name if product else f"Item {idx}")).strip()
        code = str(raw.get("snapshot_sku_or_code") or raw.get("custom_code") or "").strip()
        assigned_name = str(raw.get("assigned_name") or "").strip()
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name_snapshot=product_name[:160],
            price_snapshot=base_price,
            unit_price_override=override_decimal,
            snapshot_sku_or_code=code[:80],
            is_custom=is_custom,
            quantity=quantity,
            assigned_name=assigned_name[:80],
        )
        line_modifier_total = Decimal("0.00")
        for raw_mod in (raw.get("modifiers") or []):
            mod_name = str(raw_mod.get("name") or "").strip()
            mod_price = _to_money(raw_mod.get("price") or 0)
            if not mod_name and raw_mod.get("id"):
                db_mod = Modifier.objects.filter(id=raw_mod.get("id")).first()
                if db_mod:
                    mod_name = db_mod.name
                    mod_price = _to_money(db_mod.price)
            if not mod_name:
                continue
            OrderItemModifier.objects.create(order_item=item, modifier_name_snapshot=mod_name[:120], modifier_price_snapshot=mod_price)
            line_modifier_total += mod_price
        line_total = (base_price + line_modifier_total) * Decimal(quantity)
        subtotal += _to_money(line_total)
        requires_kitchen = requires_kitchen or bool(getattr(product, "requires_kitchen", False))

    total = _to_money(subtotal)
    tax = _to_money(total - (total / Decimal("1.13"))) if total > Decimal("0.00") else Decimal("0.00")
    order.subtotal = total
    order.tax = tax
    order.total = total
    order.discount_total = Decimal("0.00")
    order.discount_snapshot = {}
    order.disposable_total = Decimal("0.00")
    order.iva_exempt_discount = Decimal("0.00")
    order.amount_due_cents = int((total * 100).to_integral_value(rounding=ROUND_HALF_UP))
    order.requires_kitchen = requires_kitchen
    logger.info(
        "open_order.update.after_totals order_id=%s subtotal=%s discounts=%s fees=%s total=%s items=%s previous_total=%s",
        order.id,
        order.subtotal,
        order.discount_total,
        order.disposable_total,
        order.total,
        len(items_data),
        previous_total,
    )


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
        has_open_cash_session = has_open_cash_session_for_branch(branch_id)
        logger.info(
            "orders.create.cash_gate source=%s branch_id=%s has_open_cash_session=%s user_id=%s",
            source,
            branch_id,
            has_open_cash_session,
            getattr(request.user, "id", None),
        )
        if source != "kiosk" and not has_open_cash_session:
            logger.warning(
                "orders.create.cash_gate.blocked source=%s branch_id=%s user_id=%s",
                source,
                branch_id,
                getattr(request.user, "id", None),
            )
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
            qr_value=payload.get("meta", {}).get("qr_value") or payload.get("meta", {}).get("public_url"),
            receipt_context=payload.get("meta", {}).get("receipt_context"),
            suppress_qr_url_lines=True,
        )
        response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{result.filename}"'
        return response


class PendingOrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]
    pagination_class = None

    def get_queryset(self):
        ensure_whatsapp_order_columns()
        tab = str(self.request.query_params.get("tab") or "pending").strip().lower()
        if tab == "finalized":
            queryset = (
                Order.objects.filter(is_pending=False)
                .filter(
                    Q(pending_completion_type__in=["paid", "removed", "canceled"])
                    | Q(pending_reference__gt="")
                )
                .exclude(pending_completion_type="none", payment_status="unpaid", status__in=["waiting_payment", "new", "preparing", "ready"])
                .prefetch_related("items__applied_modifiers")
                .order_by("-pending_completed_at", "-updated_at")
            )
        else:
            queryset = (
                Order.objects.filter(is_pending=True)
                .exclude(status__in=["canceled", "delivered"])
                .prefetch_related("items__applied_modifiers")
                .order_by("pending_marked_at", "created_at")
            )
        branch_id = _selected_branch_id_optional(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if not has_whatsapp_order_columns():
            queryset = queryset.defer("whatsapp_num_cliente", "whatsapp_num_cliente_country")
        query = str(self.request.query_params.get("q") or "").strip()
        if query:
            search_filter = (
                Q(customer_name__icontains=query)
                | Q(pending_reference__icontains=query)
            )
            if query.isdigit():
                search_filter = search_filter | Q(order_number=int(query))
            queryset = queryset.filter(search_filter)
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = self.get_serializer(queryset, many=True).data
        for row in data:
            logger.info(
                "open_order.list.serializer_total order_id=%s subtotal=%s discounts=%s fees=%s total=%s items=%s",
                row.get("id"),
                row.get("subtotal_before_discounts"),
                row.get("discount_total"),
                row.get("disposable_total"),
                row.get("total_payable"),
                len(row.get("items") or []),
            )
        logger.info("open_order.list tab=%s count=%s branch_id=%s", str(request.query_params.get("tab") or "pending").strip().lower(), len(data), _selected_branch_id_optional(request))
        return Response({"count": len(data), "results": data}, status=status.HTTP_200_OK)


class PendingOrderToggleView(generics.GenericAPIView):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        order = Order.objects.select_for_update().get(pk=kwargs["pk"])
        is_pending = bool(request.data.get("is_pending", True))
        pending_state = str(request.data.get("pending_state") or "").strip().lower()
        auth_pin = str(request.data.get("authorization_pin") or "").strip()
        pending_reference = str(request.data.get("pending_reference") or "").strip()
        items_data = request.data.get("items") if isinstance(request.data, dict) else None
        removal_reason = str(request.data.get("removal_reason") or "").strip()
        completion_type = str(request.data.get("completion_type") or "").strip().lower()

        if order.status in {"canceled", "delivered"}:
            return Response({"detail": "La orden no está activa para Pendientes."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not is_pending and not _require_manager_pin_for_cashier(request, auth_pin):
            return Response(
                {"detail": "Autorización requerida de gerente/admin para retirar de Pendientes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if is_pending:
            if not pending_reference and not order.pending_reference:
                return Response({"detail": "Referencia requerida para enviar a Pendientes."}, status=status.HTTP_400_BAD_REQUEST)
            if pending_state not in {"pending_payment", "paid_pending_delivery", "in_kitchen", "ready"}:
                pending_state = "paid_pending_delivery" if order.payment_status == "paid" else "pending_payment"
            if isinstance(items_data, list):
                logger.info("open_order.update.request order_id=%s is_update=%s", order.id, True)
                logger.info(
                    "open_order.save.payload order_id=%s total_front=%s items=%s",
                    order.id,
                    request.data.get("total") if isinstance(request.data, dict) else None,
                    len(items_data),
                )
                _sync_pending_order_lines(order, items_data, request, auth_pin)
                logger.info(
                    "open_order.persisted_totals order_id=%s subtotal=%s discounts=%s fees=%s total=%s items=%s",
                    order.id,
                    order.subtotal,
                    order.discount_total,
                    order.disposable_total,
                    order.total,
                    len(items_data),
                )
            order.is_pending = True
            order.pending_state = pending_state
            if not order.pending_reference:
                order.pending_reference = pending_reference[:120]
            order.pending_marked_at = order.pending_marked_at or timezone.localtime(timezone.now())
            order.pending_completed_at = None
            order.pending_completion_type = "none"
            order.pending_completion_note = ""
            action = "order.pending.mark"
        else:
            if not removal_reason:
                return Response({"detail": "Motivo requerido para retirar de Pendientes."}, status=status.HTTP_400_BAD_REQUEST)
            order.is_pending = False
            order.pending_state = "none"
            order.pending_marked_at = None
            order.pending_completed_at = timezone.localtime(timezone.now())
            if completion_type not in {"paid", "removed", "canceled"}:
                completion_type = "paid" if order.payment_status == "paid" else "removed"
            order.pending_completion_type = completion_type
            order.pending_completion_note = removal_reason[:160]
            action = "order.pending.unmark"
            if completion_type == "paid":
                logger.info("open_order.finalize_paid id=%s", order.id)
            else:
                logger.info("open_order.finalize_removed id=%s completion_type=%s", order.id, completion_type)

        update_fields = [
            "is_pending",
            "pending_state",
            "pending_reference",
            "pending_marked_at",
            "pending_completed_at",
            "pending_completion_type",
            "pending_completion_note",
            "updated_at",
        ]
        if is_pending and isinstance(items_data, list):
            update_fields.extend(
                [
                    "subtotal",
                    "tax",
                    "total",
                    "discount_total",
                    "discount_snapshot",
                    "disposable_total",
                    "iva_exempt_discount",
                    "amount_due_cents",
                    "requires_kitchen",
                ]
            )
        order.save(update_fields=update_fields)
        log_audit(
            request,
            action,
            "Order",
            order.id,
            {
                "pending_state": order.pending_state,
                "is_pending": order.is_pending,
                "pending_reference": order.pending_reference,
                "removal_reason": removal_reason or None,
                "completion_type": order.pending_completion_type,
            },
        )
        return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_200_OK)
