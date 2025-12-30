from decimal import Decimal
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework import generics, status
from rest_framework.response import Response
from apps.core.audit import log_audit
from apps.core.permissions import IsCashierOrManagerOrAdmin
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer


def _total_paid(order: Order) -> Decimal:
    total = Payment.objects.filter(order=order).aggregate(
        total=Sum(
            ExpressionWrapper(
                F("amount") + F("tip_amount"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
    )["total"] or Decimal("0")
    return total


def _update_payment_status(order: Order) -> Decimal:
    total_paid = _total_paid(order)
    remaining = (order.total - total_paid).quantize(Decimal("0.01"))
    if remaining <= 0:
        order.payment_status = "paid"
    elif remaining < order.total:
        order.payment_status = "partial"
    else:
        order.payment_status = "unpaid"
    order.save(update_fields=["payment_status", "updated_at"])
    return remaining


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
        payment = serializer.save()
        remaining = _update_payment_status(payment.order)
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
        else:
            log_audit(
                request,
                "payment.partial",
                "Order",
                payment.order_id,
                {"order_id": payment.order_id, "remaining": str(remaining)},
            )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
