from decimal import Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from rest_framework import generics
from rest_framework.response import Response
from apps.core.timezone_utils import parse_business_date_range
from apps.orders.models import Order
from apps.payments.models import Payment, Refund
from apps.reports.serializers import SalesReportSerializer
from apps.core.permissions import IsAdminOrManager


class SalesReportListView(generics.ListAPIView):
    serializer_class = SalesReportSerializer
    permission_classes = [IsAdminOrManager]

    def get_queryset(self):
        queryset = Order.objects.select_related("service_type", "invoice").all()
        start_at, end_at = parse_business_date_range(
            self.request.query_params.get("date_from"),
            self.request.query_params.get("date_to"),
        )
        service_type = self.request.query_params.get("service_type")
        status = self.request.query_params.get("status")

        if start_at:
            queryset = queryset.filter(created_at__gte=start_at)
        if end_at:
            queryset = queryset.filter(created_at__lte=end_at)
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
                "service_type": (order.service_type.key if order.service_type else "SIN_TIPO"),
                "date": order.created_at,
                "subtotal": order.subtotal,
                "tax": order.tax,
                "total": order.total,
                "status": order.status,
                "discount_total": order.discount_total,
                "financial_status": order.financial_status,
                "refund_total": order.refund_total,
                "net_paid": order.net_paid,
                "sale_snapshot": (order.invoice.sale_snapshot if hasattr(order, "invoice") else {}),
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
        refund_totals = Refund.objects.filter(order__in=queryset).aggregate(
            refund_total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            refund_tips=Sum("tip_refunded"),
            refund_cash=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                filter=Q(method="cash"),
            ),
            refund_card=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                filter=Q(method="card"),
            ),
            refund_transfer=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                filter=Q(method="transfer"),
            ),
        )
        refunds_count = Refund.objects.filter(order__in=queryset).count()
        orders_paid = queryset.filter(financial_status="paid").count()
        orders_voided = queryset.filter(financial_status="voided").count()
        aggregates = {
            "count_orders": queryset.count(),
            "sum_subtotal": sum((order.subtotal for order in queryset), Decimal("0")),
            "sum_tax": sum((order.tax for order in queryset), Decimal("0")),
            "sum_total": sum((order.total for order in queryset), Decimal("0")),
            "sum_discount_total": sum((order.discount_total for order in queryset), Decimal("0")),
            "gross_total": sum((order.total for order in queryset), Decimal("0")),
            "refund_total": refund_totals["refund_total"] or Decimal("0"),
            "net_total": sum((order.total for order in queryset), Decimal("0"))
            - (refund_totals["refund_total"] or Decimal("0")),
            "payment_methods": {
                "cash": payment_totals["cash_total"] or Decimal("0"),
                "card": payment_totals["card_total"] or Decimal("0"),
                "transfer": payment_totals["transfer_total"] or Decimal("0"),
            },
            "tips_total": payment_totals["tips"] or Decimal("0"),
            "tips_net": (payment_totals["tips"] or Decimal("0")) - (refund_totals["refund_tips"] or Decimal("0")),
            "cash_total": payment_totals["cash_total"] or Decimal("0"),
            "non_cash_total": (payment_totals["card_total"] or Decimal("0"))
            + (payment_totals["transfer_total"] or Decimal("0")),
            "refunds_count": refunds_count,
            "orders_paid": orders_paid,
            "orders_voided": orders_voided,
            "refunds_by_method": {
                "cash": refund_totals["refund_cash"] or Decimal("0"),
                "card": refund_totals["refund_card"] or Decimal("0"),
                "transfer": refund_totals["refund_transfer"] or Decimal("0"),
            },
        }
        return Response({"results": serializer.data, "aggregates": aggregates})


class SalesBookJsonView(SalesReportListView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class SalesBookPdfView(SalesReportListView):
    permission_classes = [IsAdminOrManager]

    def get(self, request, *args, **kwargs):
        data = self.list(request, *args, **kwargs).data
        return Response({"message": "PDF export placeholder", "data": data})
