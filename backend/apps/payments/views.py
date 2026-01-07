from decimal import Decimal
from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from apps.core.audit import log_audit
from apps.core.permissions import IsCashierOrManagerOrAdmin, IsAdminOrManager
from apps.cashier.models import CashSession
from apps.payments.models import Payment, Refund
from apps.printing.models import PrintJob
from apps.printing.serializers import PrintJobSerializer
from apps.printing.services.jobs import create_print_job, create_refund_print_job
from apps.payments.serializers import PaymentSerializer, RefundSerializer
from apps.orders.serializers import OrderSerializer


def _get_open_session(user):
    return CashSession.objects.filter(opened_by=user, status="open").select_related("register").first()


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
        if remaining <= 0:
            log_audit(
                request,
                "payment.completed",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id},
            )
            exists = PrintJob.objects.filter(order=payment.order, type="customer", meta__event="payment.paid").exists()
            if not exists:
                create_print_job(payment.order, "customer", requested_by=request.user, event="payment.paid")
        else:
            log_audit(
                request,
                "payment.partial",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id, "remaining": str(remaining)},
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
