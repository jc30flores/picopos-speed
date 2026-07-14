from decimal import Decimal
import logging
import threading
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.audit import log_audit
from apps.core.permissions import IsCashierOrManagerOrAdmin, IsAdminOrManager, IsAdmin
from apps.cashier.models import Register, CashSession, CashTransaction
from apps.payments.models import Payment, PaymentAllocation, Refund, PaymentMethod, PaymentMethodChangeLog
from apps.printing.models import PrintJob
from apps.printing.serializers import PrintJobSerializer
from apps.printing.services.jobs import create_print_job, create_refund_print_job
from apps.printing.services.renderers import render_customer_ticket
from apps.printing.receipt_pdf import build_receipt_pdf_from_text
from apps.printing.services.system_printer import SystemPrinterService
from apps.payments.serializers import (
    PaymentSerializer,
    RefundSerializer,
    PaymentMethodSerializer,
    InternalPaymentMethodChangeSerializer,
)
from apps.orders.models import OrderItem, TableGuest, TableSession
from apps.orders.serializers import OrderSerializer
from apps.orders.services.snapshots import persist_sale_snapshot
from apps.dte.services.dte_service import (
    DTEPreflightError,
    invalidate_dte_for_order,
    send_dte_for_credit_note,
    send_dte_for_order,
)
from apps.dte.services.availability import resolve_issued_at
from apps.dte.models import DTERecord, DTEInvalidation, CreditNote
from apps.dte.runtime import get_dte_runtime_status, is_dte_config_ready
from apps.core.money import to_cents, from_cents
from apps.inventory.services import InventoryStockPolicyError, apply_inventory_for_order, reverse_inventory_for_order, validate_order_inventory_policy


logger = logging.getLogger(__name__)


def _get_open_session(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register").first()


def _is_cash_payment_method(payment_method: PaymentMethod | None) -> bool:
    if not payment_method:
        return False
    code = str(payment_method.code or "").strip().upper()
    fiscal_type = str(getattr(payment_method, "fiscal_payment_type", "") or "").strip().upper()
    return bool(fiscal_type == PaymentMethod.FISCAL_CASH or payment_method.is_cash or code in {"01", "CASH", "EFECTIVO"})


def _refund_is_cash(*, method: str, payment_method: PaymentMethod | None, original_payment: Payment | None) -> bool:
    if _is_cash_payment_method(payment_method):
        return True
    if str(method or "").strip().lower() == "cash":
        return True
    if not original_payment:
        return False
    if _is_cash_payment_method(original_payment.payment_method):
        return True
    return str(original_payment.method or "").strip().lower() == "cash"


def _venta_pdf_filename(order, *, include_seconds: bool = False) -> str:
    ts = timezone.localtime(timezone.now())
    pattern = "%Y-%m-%d_%H-%M-%S" if include_seconds else "%Y-%m-%d_%H-%M"
    return f'venta_{order.order_number}_{ts.strftime(pattern)}.pdf'


def _get_open_session_for_branch(branch_id: int) -> CashSession | None:
    return (
        CashSession.objects.filter(register__branch_id=branch_id, status="open", closed_at__isnull=True)
        .select_related("register", "register__branch")
        .order_by("-opened_at")
        .first()
    )


def _create_cash_out_for_refund(refund: Refund, user) -> tuple[CashTransaction, bool]:
    amount = (refund.amount + (refund.tip_refunded or Decimal("0"))).quantize(Decimal("0.01"))
    return CashTransaction.objects.get_or_create(
        refund=refund,
        defaults={
            "session": refund.cash_session,
            "type": "cash_out",
            "amount": amount,
            "description": f"Reembolso orden #{refund.order_id} (refund_id={refund.id})",
            "created_by": user,
        },
    )


def _create_non_cash_transaction_for_refund(refund: Refund, user) -> tuple[CashTransaction | None, bool]:
    return None, False


def _non_cash_tx_type_from_code(code: str) -> str:
    return "transfer"


def _create_transaction_for_payment(payment: Payment, user) -> tuple[CashTransaction | None, bool]:
    session = payment.cash_session
    if not session:
        return None, False
    total_amount = (payment.amount + (payment.tip_amount or Decimal("0"))).quantize(Decimal("0.01"))
    if _refund_is_cash(method=payment.method, payment_method=payment.payment_method, original_payment=None):
        tx, created = CashTransaction.objects.get_or_create(
            payment=payment,
            defaults={
                "session": session,
                "type": "cash_in",
                "amount": total_amount,
                "description": f"Pago efectivo orden #{payment.order_id} (payment_id={payment.id})",
                "created_by": user,
            },
        )
        logger.info(
            "cashier.payment.cash_in payment_id=%s session_id=%s amount=%s branch_id=%s created=%s",
            payment.id,
            tx.session_id,
            tx.amount,
            payment.order.branch_id,
            created,
        )
        return tx, created

    return None, False


def _extract_payment_allocation_payload(validated_data: dict) -> dict:
    return {
        "scope": str(validated_data.pop("payment_scope", "") or "order").strip().lower(),
        "table_session_id": validated_data.pop("table_session", None),
        "table_guest_id": validated_data.pop("table_guest", None),
        "guest_number": validated_data.pop("guest_number", None),
        "guest_label": str(validated_data.pop("guest_label", "") or "").strip(),
        "order_item_ids": list(validated_data.pop("order_item_ids", []) or []),
    }


def _order_item_total_cents(item: OrderItem) -> int:
    unit = item.unit_price_override if item.unit_price_override is not None else item.price_snapshot
    total = (unit * item.quantity) - (item.discount_amount or Decimal("0"))
    return max(to_cents(total), 0)


def _refresh_guest_paid_state(table_guest: TableGuest, order_id: int) -> None:
    guest_total_cents = sum(_order_item_total_cents(item) for item in table_guest.order_items.filter(order_id=order_id))
    paid_cents = (
        PaymentAllocation.objects.filter(payment__order_id=order_id, table_guest=table_guest).aggregate(total=Sum("amount_cents"))["total"]
        or 0
    )
    next_paid = guest_total_cents > 0 and paid_cents >= max(guest_total_cents - 1, 0)
    if table_guest.is_paid != next_paid:
        table_guest.is_paid = next_paid
        table_guest.save(update_fields=["is_paid", "updated_at"])


def _create_payment_allocations(payment: Payment, payload: dict, applied_cents: int) -> None:
    scope = str(payload.get("scope") or "order").lower()
    if scope not in {"guest", "items", "custom"} or applied_cents <= 0:
        return

    table_session = None
    if payload.get("table_session_id"):
        table_session = TableSession.objects.filter(id=payload["table_session_id"], primary_order=payment.order).first()
    if table_session is None:
        table_session = TableSession.objects.filter(primary_order=payment.order).order_by("-id").first()

    table_guest = None
    if payload.get("table_guest_id"):
        table_guest_qs = TableGuest.objects.filter(id=payload["table_guest_id"])
        if table_session:
            table_guest_qs = table_guest_qs.filter(session=table_session)
        table_guest = table_guest_qs.first()
    if table_guest is None and table_session and payload.get("guest_number"):
        table_guest = TableGuest.objects.filter(session=table_session, seat_number=payload["guest_number"]).first()

    guest_number = payload.get("guest_number") or getattr(table_guest, "seat_number", None)
    guest_label = payload.get("guest_label") or getattr(table_guest, "label", "") or (f"Persona {guest_number}" if guest_number else "")
    item_ids = [int(item_id) for item_id in payload.get("order_item_ids") or [] if str(item_id).isdigit()]
    items = list(OrderItem.objects.filter(order=payment.order, id__in=item_ids).order_by("id")) if item_ids else []

    if not items:
        PaymentAllocation.objects.create(
            payment=payment,
            table_session=table_session,
            table_guest=table_guest,
            guest_number=guest_number,
            guest_label=guest_label,
            amount=from_cents(applied_cents),
            amount_cents=applied_cents,
        )
        if table_guest:
            _refresh_guest_paid_state(table_guest, payment.order_id)
        return

    item_totals = [(item, _order_item_total_cents(item)) for item in items]
    total_item_cents = sum(cents for _, cents in item_totals) or applied_cents
    remaining = applied_cents
    for index, (item, item_cents) in enumerate(item_totals):
        if remaining <= 0:
            break
        amount_cents = remaining if index == len(item_totals) - 1 else min(remaining, round(applied_cents * (item_cents / total_item_cents)))
        if amount_cents <= 0:
            continue
        remaining -= amount_cents
        PaymentAllocation.objects.create(
            payment=payment,
            table_session=table_session,
            table_guest=table_guest or item.table_guest,
            order_item=item,
            guest_number=guest_number or getattr(item.table_guest, "seat_number", None),
            guest_label=guest_label or getattr(item.table_guest, "label", ""),
            amount=from_cents(amount_cents),
            amount_cents=amount_cents,
        )
    if table_guest:
        _refresh_guest_paid_state(table_guest, payment.order_id)




class PaymentMethodListView(generics.ListCreateAPIView):
    serializer_class = PaymentMethodSerializer

    def get_permissions(self):
        if self.request.method in {"GET", "HEAD", "OPTIONS"}:
            return [IsCashierOrManagerOrAdmin()]
        return [IsAdminOrManager()]

    def get_queryset(self):
        queryset = PaymentMethod.objects.select_related("auto_select_order_type").order_by("sort_order", "name")
        include_inactive = str(self.request.query_params.get("include_inactive", "")).lower() in {"1", "true", "yes"}
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        return queryset


class PaymentMethodDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAdminOrManager]
    queryset = PaymentMethod.objects.select_related("auto_select_order_type").all()

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        has_history = (
            instance.payments.exists()
            or instance.refunds.exists()
            or instance.payments_reporting_override.exists()
            or instance.old_payment_method_changes.exists()
            or instance.new_payment_method_changes.exists()
        )
        was_default = bool(instance.is_default)
        if has_history:
            instance.is_active = False
            instance.is_default = False
            instance.auto_select_order_type = None
            instance.save(update_fields=["is_active", "is_default", "auto_select_order_type", "updated_at"])
            self._ensure_default_after_delete_or_hide()
            serializer = self.get_serializer(instance)
            return Response(
                {
                    "detail": "Método ocultado del POS. Las ventas históricas se conservaron.",
                    "hidden": True,
                    "method": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        self.perform_destroy(instance)
        if was_default:
            self._ensure_default_after_delete_or_hide()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _ensure_default_after_delete_or_hide(self) -> None:
        PaymentMethod.objects.filter(is_active=False, is_default=True).update(is_default=False)
        if not PaymentMethod.objects.filter(is_active=True, is_default=True).exists():
            fallback = PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name").first()
            if fallback:
                fallback.is_default = True
                fallback.save(update_fields=["is_default", "updated_at"])

class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_queryset(self):
        queryset = Payment.objects.select_related("order", "received_by", "payment_method", "reporting_payment_method")
        order_id = self.request.query_params.get("order_id")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset


    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data["order"]
        allocation_payload = _extract_payment_allocation_payload(serializer.validated_data)
        branch_has_register = Register.objects.filter(branch_id=order.branch_id, is_active=True).exists()
        if branch_has_register and not _get_open_session_for_branch(order.branch_id):
            return Response(
                {"code": "CASH_SESSION_REQUIRED", "detail": "Caja no aperturada."},
                status=status.HTTP_409_CONFLICT,
            )
        order = order.__class__.objects.select_for_update().get(pk=order.pk)
        existing_applied_cents = sum(
            to_cents(p.amount_applied if p.amount_applied is not None else p.amount)
            for p in Payment.objects.select_for_update().filter(order=order)
        )
        due_cents = to_cents(order.total)
        order.amount_due_cents = due_cents
        remaining_cents = max(due_cents - existing_applied_cents, 0)
        requested_applied_cents = to_cents(serializer.validated_data.get("amount"))
        tip_cents = to_cents(serializer.validated_data.get("tip_amount"))
        method = str(serializer.validated_data.get("method") or "").strip().lower()
        payment_method = serializer.validated_data.get("payment_method")
        is_cash_payment = method == "cash" or _is_cash_payment_method(payment_method)
        if remaining_cents <= 0:
            return Response({"detail": "Order is already paid"}, status=status.HTTP_400_BAD_REQUEST)
        cash_received = serializer.validated_data.get("cash_received")
        if is_cash_payment and requested_applied_cents > remaining_cents and cash_received is None:
            cash_received = from_cents(requested_applied_cents)
            requested_applied_cents = remaining_cents
        if requested_applied_cents > remaining_cents + 1:
            return Response({"detail": "Payment exceeds remaining balance"}, status=status.HTTP_400_BAD_REQUEST)
        applied_cents = remaining_cents if requested_applied_cents > remaining_cents else requested_applied_cents
        received_cents = to_cents(cash_received) if is_cash_payment and cash_received is not None else applied_cents + tip_cents
        if is_cash_payment and received_cents < applied_cents + tip_cents:
            return Response({"detail": "Cash received must cover amount + tip"}, status=status.HTTP_400_BAD_REQUEST)
        change_cents = max(received_cents - (applied_cents + tip_cents), 0)
        will_complete_payment = applied_cents >= remaining_cents
        inventory_warning_confirmed = bool(serializer.validated_data.pop("inventory_warning_confirmed", False))
        if will_complete_payment:
            try:
                validate_order_inventory_policy(order, warning_confirmed=inventory_warning_confirmed)
            except InventoryStockPolicyError as exc:
                return Response({"code": "INVENTORY_STOCK_INSUFFICIENT", "detail": exc.message, "availability": exc.availability}, status=status.HTTP_400_BAD_REQUEST)

        if order.financial_locked_at is None:
            order.financial_locked_at = timezone.now()
            order.save(update_fields=["amount_due_cents", "financial_locked_at", "updated_at"])
        payment = serializer.save(
            cash_session=_get_open_session_for_branch(order.branch_id),
            amount=from_cents(applied_cents),
            amount_applied=from_cents(applied_cents),
            amount_received=from_cents(received_cents),
            change_amount=from_cents(change_cents),
            amount_applied_cents=applied_cents,
            amount_received_cents=received_cents,
            change_cents=change_cents,
            tip_cents=tip_cents,
            cash_received=from_cents(received_cents) if is_cash_payment else None,
        )
        _create_payment_allocations(payment, allocation_payload, applied_cents)
        _create_transaction_for_payment(payment, request.user)
        logger.info(
            "payment.created order_id=%s payment_id=%s amount=%s method=%s",
            payment.order_id,
            payment.id,
            payment.amount,
            payment.method,
        )
        payment.order.recalculate_financials()
        total_paid_cents = sum(
            to_cents(p.amount_applied if p.amount_applied is not None else p.amount)
            for p in Payment.objects.filter(order=payment.order)
        )
        remaining_cents = max((payment.order.amount_due_cents or to_cents(payment.order.total)) - total_paid_cents, 0)
        remaining = from_cents(remaining_cents)
        log_audit(
            request,
            "payment.create",
            "Payment",
            payment.id,
            {
                "order_id": payment.order_id,
                "method": payment.method,
                "amount": str(payment.amount),
                "tip_amount": str(payment.tip_amount),
            },
        )
        print_result = {"printed": False, "print_error": None, "drawer_opened": False, "drawer_error": None}
        dte_meta = {"dte_status": None, "dte_record_id": None, "dte_outbox_id": None, "dte_last_error": None}

        if remaining <= 0:
            persist_sale_snapshot(payment.order)
            try:
                apply_inventory_for_order(payment.order, user=request.user, warning_confirmed=inventory_warning_confirmed)
            except InventoryStockPolicyError as exc:
                raise ValidationError({"code": "INVENTORY_STOCK_INSUFFICIENT", "detail": exc.message, "availability": exc.availability}) from exc
            log_audit(
                request,
                "payment.completed",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id},
            )
            should_send_to_kitchen = bool(payment.order.requires_kitchen and payment.order.send_to_kitchen)
            if should_send_to_kitchen:
                if payment.order.status != "preparing":
                    payment.order.status = "preparing"
                    payment.order.save(update_fields=["status", "updated_at"])
                from apps.kitchen.models import KitchenOrderView
                KitchenOrderView.objects.get_or_create(
                    order=payment.order,
                    defaults={"service_type": payment.order.service_type, "status": "preparing"},
                )
            else:
                if payment.order.status != "delivered":
                    payment.order.status = "delivered"
                    payment.order.save(update_fields=["status", "updated_at"])
            TableSession.objects.filter(
                primary_order=payment.order,
                status__in=["open", "sent_to_kitchen", "partially_paid"],
            ).update(status=TableSession.STATUS_CLOSED, closed_by=request.user, closed_at=timezone.now(), updated_at=timezone.now())
            runtime_status = get_dte_runtime_status()
            def _after_commit_dte():
                def _enqueue_dte_async():
                    runtime = get_dte_runtime_status()
                    if not runtime.enabled:
                        logger.info("DTE_SKIP_DISABLED order_id=%s payment_id=%s", payment.order_id, payment.id)
                        dte_meta["dte_status"] = "DISABLED"
                        dte_meta["dte_last_error"] = ""
                        return
                    if not runtime.config_ready:
                        logger.info("DTE_SKIP_CONFIG_PENDING order_id=%s payment_id=%s status=%s", payment.order_id, payment.id, runtime.config_status)
                        dte_meta["dte_status"] = "CONFIG_PENDING"
                        dte_meta["dte_last_error"] = runtime.message
                        return
                    try:
                        logger.info("payment.dte.trigger order_id=%s payment_id=%s", payment.order_id, payment.id)
                        dte_record = send_dte_for_order(payment.order, payment=payment, queue_only=True)
                        persist_sale_snapshot(payment.order)
                        outbox = dte_record.outbox_entries.order_by("-created_at").first()
                        status_map = {
                            "PENDING": "QUEUED",
                            "ACCEPTED": "SENT",
                            "REJECTED": "FAILED",
                            "FAILED": "FAILED",
                        }
                        dte_meta["dte_status"] = status_map.get(dte_record.status, "QUEUED")
                        dte_meta["dte_record_id"] = dte_record.id
                        dte_meta["dte_outbox_id"] = outbox.id if outbox else None
                        dte_meta["dte_last_error"] = (outbox.error_message if outbox else "") or (dte_record.error_message or "")
                        logger.info(
                            "payment.dte.queued order_id=%s payment_id=%s dte_status=%s outbox_id=%s",
                            payment.order_id,
                            payment.id,
                            dte_record.status,
                            dte_meta["dte_outbox_id"],
                        )
                    except DTEPreflightError as exc:
                        logger.warning("payment.dte.preflight order_id=%s payment_id=%s error=%s", payment.order_id, payment.id, exc)
                        dte_meta["dte_status"] = "CONFIG_PENDING"
                        dte_meta["dte_last_error"] = str(exc)
                    except Exception as exc:  # noqa: BLE001 - fiscal send must not break payment completion
                        logger.exception("payment.dte.failed order_id=%s payment_id=%s", payment.order_id, payment.id)
                        dte_meta["dte_status"] = "FAILED"
                        dte_meta["dte_last_error"] = str(exc)
                try:
                    threading.Thread(target=_enqueue_dte_async, daemon=True, name=f"dte-enqueue-{payment.id}").start()
                except Exception:
                    _enqueue_dte_async()
            if runtime_status.enabled and runtime_status.config_ready:
                transaction.on_commit(_after_commit_dte)
            else:
                reason = "DISABLED" if not runtime_status.enabled else "CONFIG_PENDING"
                logger.info("%s order_id=%s payment_id=%s", "DTE_SKIP_DISABLED" if reason == "DISABLED" else "DTE_SKIP_CONFIG_PENDING", payment.order_id, payment.id)
                dte_meta["dte_status"] = reason
                dte_meta["dte_last_error"] = "" if reason == "DISABLED" else runtime_status.message
        else:
            TableSession.objects.filter(
                primary_order=payment.order,
                status__in=["open", "sent_to_kitchen"],
            ).update(status=TableSession.STATUS_PARTIALLY_PAID, updated_at=timezone.now())
            log_audit(
                request,
                "payment.partial",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id, "remaining": str(remaining)},
            )

        data = dict(serializer.data)
        data["printed"] = bool(print_result["printed"])
        data["print_error"] = print_result["print_error"]
        data["drawer_opened"] = bool(print_result["drawer_opened"])
        data["drawer_error"] = print_result["drawer_error"]
        if remaining <= 0 and hasattr(payment.order, "invoice"):
            data["invoice_status"] = payment.order.invoice.status
            data["invoice_id"] = payment.order.invoice.id
            data["dte_status"] = dte_meta["dte_status"] or "DISABLED"
            data["dte_record_id"] = dte_meta["dte_record_id"]
            data["dte_outbox_id"] = dte_meta["dte_outbox_id"]
            data["dte_last_error"] = dte_meta["dte_last_error"]
        return Response(data, status=status.HTTP_201_CREATED)


class PaymentInternalMethodUpdateView(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def patch(self, request, pk: int):
        payment = (
            Payment.objects.select_related("order", "payment_method", "reporting_payment_method")
            .filter(pk=pk)
            .first()
        )
        if not payment:
            return Response({"detail": "Pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        order = payment.order
        if order.financial_status in {"voided", "refunded_partial", "refunded_full"} or order.refunds.exists():
            return Response(
                {"detail": "No se puede corregir método en órdenes anuladas o con reembolso."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InternalPaymentMethodChangeSerializer(data=request.data)
        previous_method = payment.reporting_payment_method or payment.payment_method
        logger.info(
            "PAYMENT_INTERNAL_METHOD_CHANGE_REQUEST payment_id=%s order_id=%s old_method=%s requested_method_code=%s requested_method_id=%s user_id=%s",
            payment.id,
            payment.order_id,
            getattr(previous_method, "code", None),
            request.data.get("payment_method_code") or request.data.get("code") or request.data.get("payment_method"),
            request.data.get("payment_method_id") or request.data.get("method_id"),
            getattr(request.user, "id", None),
        )
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            valid_methods = serializer.context.get("valid_methods") or []
            logger.info(
                "PAYMENT_INTERNAL_METHOD_CHANGE_INVALID payment_id=%s requested_value=%s valid_active_codes=%s",
                payment.id,
                request.data.get("payment_method_code")
                or request.data.get("code")
                or request.data.get("payment_method")
                or request.data.get("payment_method_id")
                or request.data.get("method_id")
                or request.data.get("name")
                or request.data.get("label"),
                [item.get("code") for item in valid_methods],
            )
            raise
        new_method: PaymentMethod = serializer.context["new_method"]
        reason = (serializer.validated_data.get("reason") or "").strip()
        if previous_method and previous_method.id == new_method.id:
            return Response(
                {
                    "id": payment.id,
                    "order_id": payment.order_id,
                    "payment_method_code": new_method.code,
                    "payment_method_name": new_method.name,
                    "detail": f"El método de pago ya es {new_method.name}.",
                },
                status=status.HTTP_200_OK,
            )

        payment.reporting_payment_method = new_method
        payment.save(update_fields=["reporting_payment_method"])

        PaymentMethodChangeLog.objects.create(
            payment=payment,
            old_payment_method=previous_method,
            new_payment_method=new_method,
            changed_by=request.user,
            reason=reason,
        )

        log_audit(
            request,
            "payment.internal_method.change",
            "Payment",
            payment.id,
            {
                "order_id": payment.order_id,
                "old_method": previous_method.code if previous_method else None,
                "new_method": new_method.code,
                "reason": reason,
            },
        )
        logger.info(
            "PAYMENT_INTERNAL_METHOD_CHANGE_SUCCESS payment_id=%s old_method=%s new_method=%s reason_present=%s",
            payment.id,
            previous_method.code if previous_method else None,
            new_method.code,
            bool(reason),
        )

        return Response(
            {
                "id": payment.id,
                "order_id": payment.order_id,
                "payment_method_code": new_method.code,
                "payment_method_name": new_method.name,
                "detail": "Método de pago interno actualizado.",
            },
            status=status.HTTP_200_OK,
        )


class PaymentRecordRefundView(APIView):
    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        payment = Payment.objects.select_related("order", "payment_method", "reporting_payment_method").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        order = payment.order
        if order.financial_status in {"voided", "refunded_partial", "refunded_full"}:
            return Response({"detail": "La venta ya fue anulada o reembolsada."}, status=status.HTTP_400_BAD_REQUEST)

        reason = (request.data.get("reason") or "").strip() or "Reembolso desde registros"
        record = DTERecord.objects.filter(order=order, status=DTERecord.STATUS_ACCEPTED).order_by("-created_at").first()
        latest_dte = DTERecord.objects.filter(order=order).order_by("-created_at").first()
        logger.info(
            "refund.record_refund.precheck payment_id=%s order_id=%s accepted_dte_id=%s latest_dte_id=%s latest_dte_status=%s latest_error=%s",
            payment.id,
            order.id,
            getattr(record, "id", None),
            getattr(latest_dte, "id", None),
            getattr(latest_dte, "status", None),
            getattr(latest_dte, "error_message", None),
        )

        dte_action = {"action": "internal_refund"}
        fiscal_result = {"attempted": False, "success": False, "message": "Sin documento base para invalidación fiscal."}
        if not is_dte_config_ready():
            dte_base = None
            logger.info("DTE_SKIP_UNAVAILABLE refund payment_id=%s order_id=%s", payment.id, order.id)
        else:
            dte_base = record or latest_dte
        def _attempt_invalidation(*, base_record, allow_non_accepted: bool) -> dict:
            try:
                return invalidate_dte_for_order(
                    order,
                    motivo=reason,
                    responsable_dui="",
                    solicitante_dui="",
                    dte_record=base_record,
                    allow_non_accepted=allow_non_accepted,
                )
            except (DTEPreflightError, ValueError) as exc:
                logger.warning(
                    "refund.record_refund.invalidation_preflight_failed payment_id=%s order_id=%s dte_record_id=%s status=%s error=%s",
                    payment.id,
                    order.id,
                    getattr(base_record, "id", None),
                    getattr(base_record, "status", None),
                    str(exc),
                )
                return {"success": False, "status": "RECHAZADO", "error": str(exc)}

        if record and is_dte_config_ready():
            dte_type = (record.dte_type or "").upper()
            issued_at = resolve_issued_at(record)
            should_credit_note = dte_type.startswith("CCF") and (timezone.now() - issued_at).total_seconds() > 24 * 3600

            if should_credit_note:
                note = CreditNote.objects.create(
                    order=order,
                    original_dte_record=record,
                    motivo=reason,
                    total=record.total_amount,
                    dte_numero_control=record.control_number,
                    dte_codigo_generacion=record.codigo_generacion,
                    items=[],
                    status=DTERecord.STATUS_PENDING,
                )
                send_dte_for_credit_note(note)
                dte_action = {"action": "credit_note", "credit_note_id": note.id}
                fiscal_result = {"attempted": True, "success": True, "message": "Nota de crédito enviada."}
            else:
                result = _attempt_invalidation(base_record=record, allow_non_accepted=False)
                invalidation = DTEInvalidation.objects.create(
                    order=order,
                    dte_record=record,
                    motivo=reason,
                    tipo_anulacion="total",
                    status=DTERecord.STATUS_INVALIDATED if result.get("success") else DTERecord.STATUS_REJECTED,
                )
                if result.get("success"):
                    was_already_invalidated = bool(result.get("already_invalidated"))
                    dte_action = {
                        "action": "invalidate",
                        "invalidation_id": invalidation.id,
                        "message": "Refund interno e invalidación fiscal completados."
                        if not was_already_invalidated
                        else "Refund interno registrado. El DTE ya estaba invalidado fiscalmente.",
                    }
                    fiscal_result = {
                        "attempted": not was_already_invalidated,
                        "success": True,
                        "message": "Invalidación fiscal enviada."
                        if not was_already_invalidated
                        else "DTE ya invalidado previamente.",
                    }
                else:
                    dte_action = {
                        "action": "internal_refund",
                        "invalidation_id": invalidation.id,
                        "message": "Refund interno registrado, pero la invalidación fiscal fue rechazada.",
                    }
                    fiscal_result = {"attempted": True, "success": False, "message": result.get("error") or "Invalidación fiscal rechazada."}
        elif dte_base and is_dte_config_ready():
            result = _attempt_invalidation(base_record=dte_base, allow_non_accepted=True)
            invalidation = DTEInvalidation.objects.create(
                order=order,
                dte_record=dte_base,
                motivo=reason,
                tipo_anulacion="total",
                status=DTERecord.STATUS_INVALIDATED if result.get("success") else DTERecord.STATUS_REJECTED,
            )
            dte_action = {
                "action": "internal_refund",
                "invalidation_id": invalidation.id,
                "message": "Refund interno registrado. Se intentó invalidación fiscal sobre DTE no aceptado.",
            }
            fiscal_result = {
                "attempted": True,
                "success": bool(result.get("success")),
                "message": "Invalidación fiscal enviada." if result.get("success") else (result.get("error") or "Invalidación fiscal rechazada."),
            }
            logger.warning(
                "refund.record_refund.internal_plus_fiscal_attempt payment_id=%s order_id=%s latest_status=%s fiscal_success=%s",
                payment.id,
                order.id,
                getattr(dte_base, "status", None),
                fiscal_result["success"],
            )
        else:
            dte_action = {
                "action": "internal_refund",
                "message": "No existe DTE para esta venta. Se registró reembolso interno sin invalidación fiscal.",
            }

        effective_method = payment.reporting_payment_method or payment.payment_method
        cash_session = _get_open_session_for_branch(order.branch_id)
        refund_method = payment.method if payment.method in {"cash", "card", "transfer"} else "transfer"
        is_cash_refund = _refund_is_cash(method=refund_method, payment_method=effective_method, original_payment=payment)
        if is_cash_refund and not cash_session:
            return Response(
                {"detail": "No hay caja abierta para registrar el reembolso interno.", "fiscal_result": fiscal_result, **dte_action},
                status=status.HTTP_409_CONFLICT,
            )

        refund = Refund.objects.create(
            order=order,
            payment_method=effective_method,
            original_payment=payment,
            cash_session=cash_session,
            method=refund_method,
            amount=payment.amount,
            tip_refunded=payment.tip_amount or Decimal("0"),
            reason=reason,
            approved_by=request.user,
            created_by=request.user,
        )
        order.recalculate_financials()
        inventory_reversal = reverse_inventory_for_order(order, user=request.user, reason=f"Reversión por devolución de venta #{order.order_number}: {reason}")
        cash_tx = None
        if is_cash_refund:
            cash_tx, _ = _create_cash_out_for_refund(refund, request.user)
            if not cash_tx:
                raise ValueError("No se pudo registrar movimiento de caja para el reembolso.")

        log_audit(
            request,
            "payment.record_refund",
            "Refund",
            refund.id,
            {"payment_id": payment.id, "order_id": order.id, "reason": reason, **dte_action},
        )
        return Response(
            {
                "detail": "Venta reembolsada correctamente.",
                "refund_id": refund.id,
                "order": OrderSerializer(order, context={"request": request}).data,
                "cash_transaction_id": cash_tx.id if cash_tx else None,
                "fiscal_result": fiscal_result,
                "inventory_reversal": inventory_reversal,
                **dte_action,
            },
            status=status.HTTP_201_CREATED,
        )


class RefundListCreateView(generics.ListCreateAPIView):
    serializer_class = RefundSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        queryset = Refund.objects.select_related(
            "order",
            "original_payment",
            "cash_session",
            "approved_by",
            "created_by",
        )
        order_id = self.request.query_params.get("order_id")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("refund.create.bad_request errors=%s payload=%s", serializer.errors, request.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        order = validated["order"]
        original_payment = validated.get("original_payment")
        payment_method = validated.get("payment_method")
        method = validated.get("method")
        is_cash_refund = _refund_is_cash(method=method, payment_method=payment_method, original_payment=original_payment)
        cash_session = _get_open_session_for_branch(order.branch_id)
        if is_cash_refund and not cash_session:
            return Response({"detail": "No hay caja abierta para registrar el reembolso."}, status=status.HTTP_400_BAD_REQUEST)

        refund = serializer.save(
            cash_session=cash_session,
            approved_by=request.user,
            created_by=request.user,
        )
        refund.order.recalculate_financials()
        inventory_reversal = reverse_inventory_for_order(refund.order, user=request.user, reason=f"Reversión por devolución de venta #{refund.order.order_number}: {refund.reason}")
        cash_tx = None
        if is_cash_refund:
            cash_tx, created = _create_cash_out_for_refund(refund, request.user)
            logger.info(
                "cashier.refund.cash_out.created refund_id=%s session_id=%s amount=%s branch_id=%s created=%s",
                refund.id,
                cash_tx.session_id,
                cash_tx.amount,
                refund.order.branch_id,
                created,
            )
        else:
            cash_tx, _ = _create_non_cash_transaction_for_refund(refund, request.user)

        log_audit(
            request,
            "refund.create",
            "Refund",
            refund.id,
            {
                "order_id": refund.order_id,
                "amount": str(refund.amount),
                "tip_refunded": str(refund.tip_refunded),
                "method": refund.method,
                "reason": refund.reason,
                "shift_id": cash_session.id if cash_session else None,
                "approved_by": request.user.id,
                "cash_transaction_id": cash_tx.id if cash_tx else None,
            },
        )

        job = create_refund_print_job(refund, requested_by=request.user)
        return Response(
            {
                "refund": RefundSerializer(refund).data,
                "order": OrderSerializer(refund.order).data,
                "print_job": PrintJobSerializer(job).data,
                "inventory_reversal": inventory_reversal,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentPrintTicketView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, pk: int):
        payment = Payment.objects.select_related("order").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        context = {
            "order_id": payment.order_id,
            "payment_id": payment.id,
            "user_id": getattr(request.user, "id", None),
            "endpoint": "payments.print-ticket",
        }
        try:
            exists = PrintJob.objects.filter(order=payment.order, type="customer", meta__event="payment.paid").exists()
            if not exists:
                create_print_job(payment.order, "customer", requested_by=request.user, event="payment.paid")
            payload = render_customer_ticket(payment.order)
            logger.info("[TICKET_TRACE] endpoint=payments.print-ticket payment_id=%s order_id=%s", payment.id, payment.order_id)
            printer = SystemPrinterService()
            print_result = printer.print_with_pdf_fallback(
                payload.get("text", ""),
                order_id=payment.order_id,
                payment_id=payment.id,
                pdf_kwargs={
                    "logo_path": payload.get("meta", {}).get("logo_path"),
                    "qr_value": payload.get("meta", {}).get("qr_value") or payload.get("meta", {}).get("public_url"),
                    "receipt_context": payload.get("meta", {}).get("receipt_context"),
                    "suppress_qr_url_lines": True,
                },
                context=context,
                endpoint="payments.print-ticket",
            )

            drawer_opened = False
            drawer_error = None
            job = PrintJob.objects.filter(order=payment.order, type="customer").order_by("-created_at").first()
            if job:
                if print_result["receipt_pdf_path"]:
                    job.content_pdf_path = str(print_result["receipt_pdf_path"])
                if print_result["printed"]:
                    job.status = "printed"
                else:
                    job.status = "failed"
                    job.error_message = print_result["print_error"] or ""
                job.save(update_fields=["status", "content_pdf_path", "error_message"])

            if print_result["receipt_pdf_path"]:
                with open(print_result["receipt_pdf_path"], "rb") as fh:
                    pdf_bytes = fh.read()
                response = HttpResponse(pdf_bytes, content_type="application/pdf")
                response["Content-Disposition"] = f'inline; filename="{_venta_pdf_filename(payment.order)}"'
                response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response["Pragma"] = "no-cache"
                response["Expires"] = "0"
                response["X-Printed"] = "0"
                response["X-Print-Error"] = str(print_result["print_error"] or "")
                response["X-Drawer-Opened"] = "1" if drawer_opened else "0"
                response["X-Drawer-Error"] = str(drawer_error or "")
                response["X-Ticket-Fallback"] = "1"
                return response

            return Response(
                {
                    "printed": bool(print_result["printed"]),
                    "print_error": print_result["print_error"],
                    "receipt_pdf_url": print_result["receipt_pdf_url"],
                    "drawer_opened": bool(drawer_opened),
                    "drawer_error": drawer_error,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("payment.print.exception", extra={"payment_id": payment.id, "order_id": payment.order_id})
            return Response({"printed": False, "print_error": str(exc), "drawer_opened": False, "drawer_error": None}, status=status.HTTP_200_OK)


class PaymentTicketPDFView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def perform_content_negotiation(self, request, force=False):
        renderer = self.get_renderers()[0]
        return renderer, renderer.media_type

    def get(self, request, pk: int):
        payment = Payment.objects.select_related("order").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            payload = render_customer_ticket(payment.order)
            logger.info("[TICKET_TRACE] endpoint=payments.ticket-pdf payment_id=%s order_id=%s", payment.id, payment.order_id)
            filename = _venta_pdf_filename(payment.order)
            result = build_receipt_pdf_from_text(
                text=payload.get("text", ""),
                filename=filename,
                logo_path=payload.get("meta", {}).get("logo_path"),
                qr_value=payload.get("meta", {}).get("qr_value") or payload.get("meta", {}).get("public_url"),
                receipt_context=payload.get("meta", {}).get("receipt_context"),
                suppress_qr_url_lines=True,
            )
            response = HttpResponse(result.pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="{result.filename}"'
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
            return response
        except ModuleNotFoundError as exc:
            logger.exception("payment.ticket_pdf.dependency_missing payment_id=%s", payment.id)
            return Response(
                {"detail": f"No se pudo generar el PDF: dependencia faltante ({exc})."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception:
            logger.exception("payment.ticket_pdf.failed payment_id=%s", payment.id)
            return Response({"detail": "No se pudo generar el ticket PDF."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
