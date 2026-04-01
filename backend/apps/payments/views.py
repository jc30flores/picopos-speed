from decimal import Decimal
import logging
import threading
from django.db import transaction
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.core.audit import log_audit
from apps.core.permissions import IsCashierOrManagerOrAdmin, IsAdminOrManager
from apps.cashier.models import CashSession, CashTransaction
from apps.payments.models import Payment, Refund, PaymentMethod
from apps.printing.models import PrintJob
from apps.printing.serializers import PrintJobSerializer
from apps.printing.services.jobs import create_print_job, create_refund_print_job
from apps.printing.services.renderers import render_customer_ticket
from apps.printing.services.usb_printer import USBPrinterService
from apps.payments.serializers import PaymentSerializer, RefundSerializer, PaymentMethodSerializer
from apps.orders.serializers import OrderSerializer
from apps.orders.services.snapshots import persist_sale_snapshot
from apps.dte.services.dte_service import send_dte_for_order
from apps.cashier.services import CashDrawerService


logger = logging.getLogger(__name__)


def _get_open_session(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register").first()


def _is_cash_payment_method(payment_method: PaymentMethod | None) -> bool:
    if not payment_method:
        return False
    code = str(payment_method.code or "").strip().upper()
    return bool(payment_method.is_cash or code in {"01", "CASH", "EFECTIVO"})


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




class PaymentMethodListView(generics.ListAPIView):
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_queryset(self):
        return PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name")

class PaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_queryset(self):
        queryset = Payment.objects.select_related("order", "received_by")
        order_id = self.request.query_params.get("order_id")
        if order_id:
            queryset = queryset.filter(order_id=order_id)
        return queryset

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save(
            cash_session=_get_open_session(request.user),
        )
        logger.info(
            "payment.created order_id=%s payment_id=%s amount=%s method=%s",
            payment.order_id,
            payment.id,
            payment.amount,
            payment.method,
        )
        payment.order.recalculate_financials()
        total_paid = payment.order.net_paid + payment.order.refund_total
        remaining = (payment.order.total - total_paid).quantize(Decimal("0.01"))
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
            def _after_commit_dte():
                def _enqueue_dte_async():
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
                    except Exception as exc:  # noqa: BLE001 - fiscal send must not break payment completion
                        logger.exception("payment.dte.failed order_id=%s payment_id=%s", payment.order_id, payment.id)
                        dte_meta["dte_status"] = "FAILED"
                        dte_meta["dte_last_error"] = str(exc)
                try:
                    threading.Thread(target=_enqueue_dte_async, daemon=True, name=f"dte-enqueue-{payment.id}").start()
                except Exception:
                    _enqueue_dte_async()
            transaction.on_commit(_after_commit_dte)
            if payment.method == "cash":
                try:
                    drawer_result = CashDrawerService().open_drawer()
                    print_result["drawer_opened"] = bool(drawer_result.success)
                    if not drawer_result.success:
                        print_result["drawer_error"] = drawer_result.message or drawer_result.error
                except Exception as drawer_exc:  # noqa: BLE001
                    print_result["drawer_error"] = str(drawer_exc)
        else:
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
            data["dte_status"] = dte_meta["dte_status"] or "QUEUED"
            data["dte_record_id"] = dte_meta["dte_record_id"]
            data["dte_outbox_id"] = dte_meta["dte_outbox_id"]
            data["dte_last_error"] = dte_meta["dte_last_error"]
        return Response(data, status=status.HTTP_201_CREATED)


class RefundListCreateView(generics.ListCreateAPIView):
    serializer_class = RefundSerializer
    permission_classes = [IsAdminOrManager]

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
        cash_session = _get_open_session_for_branch(order.branch_id) if is_cash_refund else None
        if is_cash_refund and not cash_session:
            return Response({"detail": "No hay caja abierta para registrar el reembolso."}, status=status.HTTP_400_BAD_REQUEST)

        refund = serializer.save(
            cash_session=cash_session,
            approved_by=request.user,
            created_by=request.user,
        )
        refund.order.recalculate_financials()
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
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentPrintTicketView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request, pk: int):
        payment = Payment.objects.select_related("order").filter(pk=pk).first()
        if not payment:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            exists = PrintJob.objects.filter(order=payment.order, type="customer", meta__event="payment.paid").exists()
            if not exists:
                create_print_job(payment.order, "customer", requested_by=request.user, event="payment.paid")
            payload = render_customer_ticket(payment.order)
            printed, print_error = USBPrinterService().print_receipt(payload)
            return Response({"printed": bool(printed), "print_error": print_error}, status=status.HTTP_200_OK)
        except Exception as exc:  # noqa: BLE001
            logger.exception("payment.print.exception", extra={"payment_id": payment.id, "order_id": payment.order_id})
            return Response({"printed": False, "print_error": str(exc)}, status=status.HTTP_200_OK)
