from decimal import Decimal
import logging
from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from apps.core.audit import log_audit
from apps.core.permissions import IsCashierOrManagerOrAdmin, IsAdminOrManager
from apps.cashier.models import CashSession
from apps.payments.models import Payment, Refund, PaymentMethod
from apps.printing.models import PrintJob
from apps.printing.serializers import PrintJobSerializer
from apps.printing.services.jobs import create_print_job, create_refund_print_job
from apps.printing.services.renderers import render_customer_ticket
from apps.printing.services.usb_printer import USBPrinterService
from apps.payments.serializers import PaymentSerializer, RefundSerializer, PaymentMethodSerializer
from apps.orders.serializers import OrderSerializer
from apps.dte.services import transmit_sale_dte
from apps.cashier.services import CashDrawerService


logger = logging.getLogger(__name__)


def _get_open_session(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register").first()




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

        if remaining <= 0:
            log_audit(
                request,
                "payment.completed",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id},
            )
            if payment.order.requires_kitchen:
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
            try:
                logger.info("payment.dte.trigger order_id=%s payment_id=%s", payment.order_id, payment.id)
                print(f"[DTE] Trigger send_dte for order={payment.order_id} payment={payment.id} branch={payment.order.branch_id}")
                dte_record = transmit_sale_dte(payment.order_id, source="normal_send", payment_id=payment.id)
                log_audit(
                    request,
                    "invoice.processed",
                    "DTERecord",
                    dte_record.id,
                    {"order_id": payment.order_id, "status": dte_record.status},
                )
            except Exception as exc:  # noqa: BLE001 - fiscal send must not break payment completion
                log_audit(
                    request,
                    "invoice.failed_non_blocking",
                    "Order",
                    payment.order_id,
                    {"order_id": payment.order_id, "error": str(exc)},
                )
            exists = PrintJob.objects.filter(order=payment.order, type="customer", meta__event="payment.paid").exists()
            if not exists:
                create_print_job(payment.order, "customer", requested_by=request.user, event="payment.paid")

            def _after_commit_print():
                try:
                    payload = render_customer_ticket(payment.order)
                    printed, print_error = USBPrinterService().print_text(payload["text"])
                    print_result["printed"] = printed
                    print_result["print_error"] = print_error
                    if payment.method == "cash":
                        try:
                            CashDrawerService().open_drawer()
                            print_result["drawer_opened"] = True
                        except Exception as drawer_exc:  # noqa: BLE001
                            print_result["drawer_error"] = str(drawer_exc)
                    if printed:
                        logger.info("payment.print.success", extra={"payment_id": payment.id, "order_id": payment.order_id})
                    else:
                        logger.warning(
                            "payment.print.failed",
                            extra={"payment_id": payment.id, "order_id": payment.order_id, "print_error": print_error},
                        )
                except Exception as exc:  # noqa: BLE001
                    print_result["printed"] = False
                    print_result["print_error"] = str(exc)
                    logger.exception("payment.print.exception", extra={"payment_id": payment.id, "order_id": payment.order_id})

            transaction.on_commit(_after_commit_print)
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
        cash_session = _get_open_session(request.user)
        if not cash_session:
            return Response({"detail": "Open shift required"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refund = serializer.save(
            cash_session=cash_session,
            approved_by=request.user,
            created_by=request.user,
        )
        refund.order.recalculate_financials()

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
                "shift_id": cash_session.id,
                "approved_by": request.user.id,
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
