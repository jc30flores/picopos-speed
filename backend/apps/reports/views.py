from django.utils.dateparse import parse_date
from decimal import Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from rest_framework import generics
from rest_framework.response import Response
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.reports.serializers import SalesReportSerializer
from apps.core.permissions import IsAdminOrManager


class SalesReportListView(generics.ListAPIView):
    serializer_class = SalesReportSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = Order.objects.select_related("service_type").all()
        date_from = parse_date(self.request.query_params.get("date_from") or "")
        date_to = parse_date(self.request.query_params.get("date_to") or "")
        service_type = self.request.query_params.get("service_type")
        status = self.request.query_params.get("status")

        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)
        if service_type:
            queryset = queryset.filter(service_type__key=service_type)
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [
            {
                "order_id": order.id,
                "order_number": order.order_number,
                "service_type": order.service_type.key,
                "date": order.created_at,
                "subtotal": order.subtotal,
                "tax": order.tax,
                "total": order.total,
                "status": order.status,
                "discount_total": order.discount_total,
            }
            for order in queryset
        ]
        serializer = self.get_serializer(data, many=True)
        payment_totals = Payment.objects.filter(order__in=queryset).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            tips=Sum("tip_amount"),
            cash_total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                filter=Q(method="cash"),
            ),
            card_total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                filter=Q(method="card"),
            ),
            transfer_total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                filter=Q(method="transfer"),
            ),
        )
        aggregates = {
            "count_orders": queryset.count(),
            "sum_subtotal": sum((order.subtotal for order in queryset), Decimal("0")),
            "sum_tax": sum((order.tax for order in queryset), Decimal("0")),
            "sum_total": sum((order.total for order in queryset), Decimal("0")),
            "sum_discount_total": sum((order.discount_total for order in queryset), Decimal("0")),
            "payment_methods": {
                "cash": payment_totals["cash_total"] or Decimal("0"),
                "card": payment_totals["card_total"] or Decimal("0"),
                "transfer": payment_totals["transfer_total"] or Decimal("0"),
            },
            "tips_total": payment_totals["tips"] or Decimal("0"),
            "cash_total": payment_totals["cash_total"] or Decimal("0"),
            "non_cash_total": (payment_totals["card_total"] or Decimal("0"))
            + (payment_totals["transfer_total"] or Decimal("0")),
        }
        return Response({"results": serializer.data, "aggregates": aggregates})
