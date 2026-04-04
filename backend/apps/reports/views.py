from decimal import Decimal, ROUND_HALF_UP

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.models import ServiceType
from apps.core.permissions import IsCashierOrManagerOrAdmin
from apps.core.service_types import SERVICE_TYPE_LABELS, normalize_service_type
from apps.payments.models import Payment, Refund
from apps.payments.normalization import PAYMENT_METHOD_LABELS, payment_code_from_payment
from apps.reports.serializers import SalesReportSerializer

MONEY_Q = Decimal("0.01")

def q2(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(MONEY_Q, rounding=ROUND_HALF_UP)

class SalesReportListView(generics.ListAPIView):
    serializer_class = SalesReportSerializer
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get_queryset(self):
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if not date_from or not date_to:
            raise ValidationError({"detail": "date_from y date_to son obligatorios (YYYY-MM-DD)."})

        from_date = parse_date(date_from)
        to_date = parse_date(date_to)
        if not from_date or not to_date:
            raise ValidationError({"detail": "Formato de fecha inválido. Use YYYY-MM-DD."})

        start = f"{from_date.isoformat()} 00:00:00"
        end = f"{to_date.isoformat()} 23:59:59.999999"
        queryset = Payment.objects.select_related("order", "order__service_type", "order__invoice", "payment_method", "reporting_payment_method").filter(
            created_at__gte=start,
            created_at__lte=end,
        )

        search = (self.request.query_params.get("q") or self.request.query_params.get("search") or "").strip()
        payment_method = (self.request.query_params.get("payment_method") or "").strip().lower()
        service_type = normalize_service_type(self.request.query_params.get("service_type")) if self.request.query_params.get("service_type") else ""
        status = self.request.query_params.get("status")

        if payment_method:
            if payment_method == "card_debit":
                queryset = queryset.filter(
                    Q(reporting_payment_method__code__iexact="card_debit")
                    | Q(reporting_payment_method__code__iexact="card", card_type="debit")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card_debit")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card", card_type="debit")
                )
            elif payment_method == "card_credit":
                queryset = queryset.filter(
                    Q(reporting_payment_method__code__iexact="card_credit")
                    | Q(reporting_payment_method__code__iexact="card", card_type="credit")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card_credit")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card", card_type="credit")
                    | Q(reporting_payment_method__isnull=True, payment_method__isnull=True, method="card", card_type="credit")
                )
            else:
                q = Q(reporting_payment_method__code__iexact=payment_method) | Q(
                    reporting_payment_method__isnull=True, payment_method__code__iexact=payment_method
                )
                if payment_method == "cash":
                    q = q | Q(reporting_payment_method__isnull=True, payment_method__isnull=True, method="cash")
                queryset = queryset.filter(q)

        if service_type:
            matching_service_type_ids = [
                service.id
                for service in ServiceType.objects.only("id", "key", "label")
                if normalize_service_type(service.key, default="") == service_type
                or normalize_service_type(service.label, default="") == service_type
            ]
            queryset = queryset.filter(order__service_type_id__in=matching_service_type_ids)
        if status:
            queryset = queryset.filter(order__status=status)
        if search:
            queryset = queryset.filter(
                Q(order__order_number__icontains=search)
                | Q(order__customer_name__icontains=search)
                | Q(order__invoice__numero_control__icontains=search)
            )
        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        rows = []
        for payment in queryset:
            order = payment.order
            pm_code = payment_code_from_payment(payment)
            st_code = normalize_service_type(order.service_type.key if order.service_type_id else None)
            rows.append(
                {
                    "payment_id": payment.id,
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "created_at": payment.created_at,
                    "customer_name": order.customer_name,
                    "service_type_code": st_code,
                    "service_type_label": SERVICE_TYPE_LABELS.get(st_code, st_code.upper()),
                    "payment_method_code": pm_code,
                    "payment_method_label": PAYMENT_METHOD_LABELS.get(pm_code, pm_code),
                    "total_amount": f"{q2(payment.amount + (payment.tip_amount or Decimal('0'))):.2f}",
                    "status": order.status,
                    "financial_status": order.financial_status,
                    "control_number": order.invoice.numero_control if hasattr(order, "invoice") else "",
                }
            )

        serializer = self.get_serializer(rows, many=True)
        method_totals = {code: Decimal("0") for code in PAYMENT_METHOD_LABELS.keys()}
        for row in rows:
            method_totals[row["payment_method_code"]] = q2(method_totals[row["payment_method_code"]] + Decimal(row["total_amount"]))

        refunds = Refund.objects.filter(order_id__in=[r["order_id"] for r in rows]).aggregate(
            total=Sum(ExpressionWrapper(F("amount") + F("tip_refunded"), output_field=DecimalField(max_digits=12, decimal_places=2)))
        )
        gross = sum((Decimal(r["total_amount"]) for r in rows), Decimal("0"))
        refund_total = q2(refunds["total"])
        net = q2(gross - refund_total)
        return Response(
            {
                "results": serializer.data,
                "aggregates": {
                    "count_orders": len(rows),
                    "sum_total": f"{q2(gross):.2f}",
                    "refund_total": f"{refund_total:.2f}",
                    "net_total": f"{net:.2f}",
                    "payment_methods": {k: f"{q2(v):.2f}" for k, v in method_totals.items()},
                },
            }
        )


class SalesBookJsonView(SalesReportListView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class SalesBookPdfView(SalesReportListView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request, *args, **kwargs):
        data = self.list(request, *args, **kwargs).data
        return Response({"message": "PDF export placeholder", "data": data})
