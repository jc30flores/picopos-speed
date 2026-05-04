from calendar import monthrange
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, CharField, Count, DecimalField, DurationField, ExpressionWrapper, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDay, TruncHour, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import ServiceType
from apps.core.permissions import IsCashierOrManagerOrAdmin
from apps.core.service_types import SERVICE_TYPE_LABELS, normalize_service_type
from apps.orders.models import OrderItem, OrderItemModifier
from apps.payments.models import Payment, Refund
from apps.employees.models import AttendanceRecord, AttendanceCycle, AttendanceBreak, Employee, AttendanceCycleAdjustment
from apps.employees.attendance_utils import duration_seconds, sum_cycle_break_seconds, cycle_break_seconds_for_reports
from apps.payments.normalization import PAYMENT_METHOD_LABELS, payment_code_from_payment
from apps.printing.services.renderers import render_customer_ticket
from apps.reports.serializers import SalesReportSerializer
import logging

logger = logging.getLogger(__name__)

MONEY_Q = Decimal("0.01")

def q2(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def _safe_replace_year(d, year: int):
    try:
        return d.replace(year=year)
    except ValueError:
        if d.month == 2 and d.day == 29:
            return d.replace(year=year, month=2, day=28)
        raise


def _shift_months(d, months: int):
    month_idx = d.month - 1 + months
    target_year = d.year + (month_idx // 12)
    target_month = month_idx % 12 + 1
    target_day = min(d.day, monthrange(target_year, target_month)[1])
    return d.replace(year=target_year, month=target_month, day=target_day)


def _parse_report_dates(request):
    start_raw = request.query_params.get("start") or request.query_params.get("date_from")
    end_raw = request.query_params.get("end") or request.query_params.get("date_to")
    if not start_raw or not end_raw:
        raise ValidationError({"detail": "start y end son obligatorios (YYYY-MM-DD)."})

    start_date = parse_date(start_raw)
    end_date = parse_date(end_raw)
    if not start_date or not end_date:
        raise ValidationError({"detail": "Formato de fecha inválido. Use YYYY-MM-DD."})
    if end_date < start_date:
        raise ValidationError({"detail": "end debe ser mayor o igual a start."})
    return start_date, end_date


def _parse_csv_ids(raw_value: str | None, field_name: str):
    if not raw_value:
        return []
    values = [v.strip() for v in raw_value.split(",") if v.strip()]
    try:
        return [int(v) for v in values]
    except ValueError as exc:
        raise ValidationError({field_name: "Debe contener IDs numéricos separados por coma."}) from exc


def _range_to_datetimes(start_date, end_date):
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), timezone=tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max), timezone=tz)
    return start_dt, end_dt


def _comparison_range(start_date, end_date, mode: str, group_by: str | None):
    if mode == "none":
        return None
    if mode == "previous_year":
        return _safe_replace_year(start_date, start_date.year - 1), _safe_replace_year(end_date, end_date.year - 1)

    day_span = (end_date - start_date).days + 1
    if group_by == "hour" or day_span == 1:
        return start_date - timedelta(days=7), end_date - timedelta(days=7)
    if group_by == "week":
        return start_date - timedelta(days=7), end_date - timedelta(days=7)
    if group_by == "month":
        return _shift_months(start_date, -1), _shift_months(end_date, -1)
    if group_by == "year":
        return _safe_replace_year(start_date, start_date.year - 1), _safe_replace_year(end_date, end_date.year - 1)
    return start_date - timedelta(days=day_span), end_date - timedelta(days=day_span)


def _payment_method_code_expression():
    return Case(
        When(reporting_payment_method__code__iexact="card", then=Value("card")),
        When(reporting_payment_method__code__iexact="credit_card", then=Value("card")),
        When(reporting_payment_method__code__iexact="debit_card", then=Value("card")),
        When(reporting_payment_method__code__iexact="card_credit", then=Value("card")),
        When(reporting_payment_method__code__iexact="card_debit", then=Value("card")),
        When(reporting_payment_method__code__iexact="efectivo", then=Value("cash")),
        When(reporting_payment_method__code__iexact="01", then=Value("cash")),
        When(reporting_payment_method__code__iexact="pedidosya", then=Value("pedidos_ya")),
        When(reporting_payment_method__isnull=False, then=F("reporting_payment_method__code")),
        When(payment_method__code__iexact="card", then=Value("card")),
        When(payment_method__code__iexact="credit_card", then=Value("card")),
        When(payment_method__code__iexact="debit_card", then=Value("card")),
        When(payment_method__code__iexact="card_credit", then=Value("card")),
        When(payment_method__code__iexact="card_debit", then=Value("card")),
        When(payment_method__code__iexact="efectivo", then=Value("cash")),
        When(payment_method__code__iexact="01", then=Value("cash")),
        When(payment_method__code__iexact="pedidosya", then=Value("pedidos_ya")),
        When(payment_method__isnull=False, then=F("payment_method__code")),
        When(method__iexact="cash", then=Value("cash")),
        When(method__iexact="card", then=Value("card")),
        default=Value("transfer"),
        output_field=CharField(),
    )


def _parse_csv_values(raw_value: str | None):
    if not raw_value:
        return []
    return [value.strip() for value in str(raw_value).split(",") if value.strip()]


def _apply_common_filters(queryset, request):
    category_ids = _parse_csv_ids(request.query_params.get("category_ids"), "category_ids")
    product_ids = _parse_csv_ids(request.query_params.get("product_ids"), "product_ids")
    modifier_ids = _parse_csv_ids(request.query_params.get("modifier_ids"), "modifier_ids")
    order_types = _parse_csv_values(request.query_params.get("service_types") or request.query_params.get("order_types"))
    if request.query_params.get("order_type"):
        order_types.append(request.query_params.get("order_type"))
    payment_methods = _parse_csv_values(request.query_params.get("payment_methods"))
    if request.query_params.get("payment_method"):
        payment_methods.append(request.query_params.get("payment_method"))

    if category_ids:
        queryset = queryset.filter(order__items__product__category_id__in=category_ids)
    if product_ids:
        queryset = queryset.filter(order__items__product_id__in=product_ids)
    if modifier_ids:
        queryset = queryset.filter(order__items__applied_modifiers__id__in=modifier_ids)
    normalized_order_types = {normalize_service_type(value) for value in order_types if value}
    if normalized_order_types:
        matching_service_type_ids = [
            service.id
            for service in ServiceType.objects.only("id", "key", "label")
            if normalize_service_type(service.key, default="") in normalized_order_types
            or normalize_service_type(service.label, default="") in normalized_order_types
        ]
        queryset = queryset.filter(order__service_type_id__in=matching_service_type_ids)
    normalized_payment_methods = {value.strip().lower() for value in payment_methods if value}
    if normalized_payment_methods:
        queryset = queryset.annotate(_payment_code=_payment_method_code_expression()).filter(_payment_code__in=normalized_payment_methods)
    return queryset.distinct()


def _kpis_for_queryset(queryset):
    totals = queryset.aggregate(
        total=Sum(ExpressionWrapper(F("amount") + Coalesce(F("tip_amount"), Value(Decimal("0.00"))), output_field=DecimalField(max_digits=12, decimal_places=2))),
        count=Count("id"),
    )
    total = q2(totals["total"])
    count = int(totals["count"] or 0)
    avg = q2((total / count) if count else Decimal("0"))
    return {"total": f"{total:.2f}", "count": count, "avg_ticket": f"{avg:.2f}"}

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

        start, end = _range_to_datetimes(from_date, to_date)
        queryset = Payment.objects.select_related("order", "order__service_type", "order__invoice", "payment_method", "reporting_payment_method").filter(
            created_at__gte=start,
            created_at__lte=end,
        )

        search = (self.request.query_params.get("q") or self.request.query_params.get("search") or "").strip()
        payment_method = (self.request.query_params.get("payment_method") or "").strip().lower()
        service_type = normalize_service_type(self.request.query_params.get("service_type")) if self.request.query_params.get("service_type") else ""
        status = self.request.query_params.get("status")

        if payment_method:
            if payment_method in {"card", "card_debit", "card_credit"}:
                queryset = queryset.filter(
                    Q(reporting_payment_method__code__iexact="card")
                    | Q(reporting_payment_method__code__iexact="card_debit")
                    | Q(reporting_payment_method__code__iexact="card_credit")
                    | Q(reporting_payment_method__code__iexact="debit_card")
                    | Q(reporting_payment_method__code__iexact="credit_card")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card_debit")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="card_credit")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="debit_card")
                    | Q(reporting_payment_method__isnull=True, payment_method__code__iexact="credit_card")
                    | Q(reporting_payment_method__isnull=True, payment_method__isnull=True, method="card")
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
        queryset = _apply_common_filters(queryset, self.request)
        return queryset.order_by("-created_at", "-id")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        rows = []
        seen_payment_ids: set[int] = set()
        for payment in queryset:
            if payment.id in seen_payment_ids:
                continue
            seen_payment_ids.add(payment.id)
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


class SalesTimeseriesView(generics.GenericAPIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    GROUP_MAP = {
        "hour": TruncHour,
        "day": TruncDay,
        "week": TruncWeek,
        "month": TruncMonth,
        "year": TruncYear,
    }

    def _series(self, queryset, group_by: str):
        trunc_fn = self.GROUP_MAP[group_by]
        tz = timezone.get_current_timezone()
        rows = (
            queryset.annotate(bucket=trunc_fn("created_at", tzinfo=tz))
            .values("bucket")
            .annotate(
                total=Sum(
                    ExpressionWrapper(
                        F("amount") + Coalesce(F("tip_amount"), Value(Decimal("0.00"))),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                count=Count("id"),
            )
            .order_by("bucket")
        )
        return [{"key": row["bucket"].isoformat(), "total": f"{q2(row['total']):.2f}", "count": int(row["count"] or 0)} for row in rows]

    def get(self, request, *args, **kwargs):
        """
        Query params supported:
        - start|date_from (YYYY-MM-DD)
        - end|date_to (YYYY-MM-DD)
        - group_by|granularity: hour|day|week|month|year (also accepts hours)
        - compare|compare_with: none|previous_period|previous_year|previous_week
        - optional filters: category_ids, product_ids, modifier_ids, service_types/order_type, payment_methods/payment_method
        """
        start_date, end_date = _parse_report_dates(request)
        granularity = (request.query_params.get("group_by") or request.query_params.get("granularity") or "day").strip().lower()
        group_by = "hour" if granularity == "hours" else granularity
        if group_by not in self.GROUP_MAP:
            raise ValidationError({"group_by": "Debe ser uno de: hour, day, week, month, year."})
        compare_mode = (request.query_params.get("compare") or request.query_params.get("compare_with") or "none").strip().lower()
        if compare_mode == "previous_week":
            compare_mode = "previous_period"
            group_by = "week" if group_by in {"day", "week"} else group_by
        if compare_mode not in {"none", "previous_period", "previous_year"}:
            raise ValidationError({"compare": "Debe ser none, previous_period, previous_week o previous_year."})

        start_dt, end_dt = _range_to_datetimes(start_date, end_date)
        base_qs = Payment.objects.select_related("order", "order__service_type", "payment_method", "reporting_payment_method").filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        base_qs = _apply_common_filters(base_qs, request)
        payload = {
            "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "group_by": group_by,
            "series": self._series(base_qs, group_by),
            "kpis": _kpis_for_queryset(base_qs),
            "compare": {"mode": compare_mode},
            "compare_kpis": {"total": "0.00", "count": 0, "avg_ticket": "0.00"},
        }

        compare_range = _comparison_range(start_date, end_date, compare_mode, group_by)
        if compare_range:
            compare_start, compare_end = compare_range
            compare_start_dt, compare_end_dt = _range_to_datetimes(compare_start, compare_end)
            compare_qs = Payment.objects.select_related("order", "order__service_type", "payment_method", "reporting_payment_method").filter(
                created_at__gte=compare_start_dt,
                created_at__lte=compare_end_dt,
            )
            compare_qs = _apply_common_filters(compare_qs, request)
            payload["compare"] = {
                "mode": compare_mode,
                "range": {"start": compare_start.isoformat(), "end": compare_end.isoformat()},
                "series": self._series(compare_qs, group_by),
            }
            payload["compare_kpis"] = _kpis_for_queryset(compare_qs)
        return Response(payload)


class SalesBreakdownView(generics.GenericAPIView):
    permission_classes = [IsCashierOrManagerOrAdmin]
    DIMENSIONS = {"category", "product", "order_type", "payment_method", "modifier"}

    def _serialize_items(self, rows):
        totals_sum = sum((q2(row["total"]) for row in rows), Decimal("0"))
        items = []
        for row in rows:
            total = q2(row["total"])
            pct = (total / totals_sum) if totals_sum > 0 else Decimal("0")
            items.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "total": f"{total:.2f}",
                    "count": int(row["count"] or 0),
                    "pct": float(pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)),
                }
            )
        return items

    def _breakdown(self, payments_qs, dimension: str):
        order_ids = payments_qs.values("order_id")
        item_total_expr = ExpressionWrapper(
            F("quantity") * Coalesce(F("unit_price_override"), F("price_snapshot")) - Coalesce(F("discount_amount"), Value(Decimal("0.00"))),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        if dimension == "order_type":
            rows = (
                payments_qs.values("order__service_type_id", "order__service_type__label", "order__service_type__key")
                .annotate(
                    total=Sum(
                        ExpressionWrapper(
                            F("amount") + Coalesce(F("tip_amount"), Value(Decimal("0.00"))),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                    count=Count("id"),
                )
                .order_by("-total")
            )
            return self._serialize_items(
                [
                    {
                        "id": row["order__service_type_id"] or 0,
                        "name": row["order__service_type__label"]
                        or SERVICE_TYPE_LABELS.get(normalize_service_type(row["order__service_type__key"]), "Sin tipo"),
                        "total": row["total"],
                        "count": row["count"],
                    }
                    for row in rows
                ]
            )
        if dimension == "payment_method":
            rows = (
                payments_qs.annotate(payment_code=_payment_method_code_expression())
                .values("payment_code")
                .annotate(
                    total=Sum(
                        ExpressionWrapper(
                            F("amount") + Coalesce(F("tip_amount"), Value(Decimal("0.00"))),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                    count=Count("id"),
                )
                .order_by("-total")
            )
            return self._serialize_items(
                [
                    {
                        "id": row["payment_code"],
                        "name": PAYMENT_METHOD_LABELS.get(row["payment_code"], row["payment_code"] or "Sin método"),
                        "total": row["total"],
                        "count": row["count"],
                    }
                    for row in rows
                ]
            )
        if dimension == "category":
            rows = (
                OrderItem.objects.filter(order_id__in=order_ids, product__isnull=False)
                .values("product__category_id", "product__category__name")
                .annotate(total=Sum(item_total_expr), count=Sum("quantity"))
                .order_by("-total")
            )
            return self._serialize_items([{"id": row["product__category_id"], "name": row["product__category__name"] or "Sin categoría", "total": row["total"], "count": row["count"]} for row in rows])
        if dimension == "product":
            rows = (
                OrderItem.objects.filter(order_id__in=order_ids)
                .values("product_id", "product__name", "product_name_snapshot")
                .annotate(total=Sum(item_total_expr), count=Sum("quantity"))
                .order_by("-total")
            )
            return self._serialize_items(
                [
                    {
                        "id": row["product_id"] or 0,
                        "name": row["product__name"] or row["product_name_snapshot"] or "Producto",
                        "total": row["total"],
                        "count": row["count"],
                    }
                    for row in rows
                ]
            )
        rows = (
            OrderItemModifier.objects.filter(order_item__order_id__in=order_ids)
            .values("id", "modifier_name_snapshot")
            .annotate(total=Sum("modifier_price_snapshot"), count=Count("id"))
            .order_by("-total")
        )
        return self._serialize_items([{"id": row["id"], "name": row["modifier_name_snapshot"] or "Modificador", "total": row["total"], "count": row["count"]} for row in rows])

    def get(self, request, *args, **kwargs):
        """
        Query params supported:
        - start|date_from, end|date_to
        - dimension: category|product|order_type|payment_method|modifier
        - compare|compare_with: none|previous_period|previous_year|previous_week
        - optional filters: category_ids, product_ids, modifier_ids, service_types/order_type, payment_methods/payment_method
        """
        start_date, end_date = _parse_report_dates(request)
        dimension = (request.query_params.get("dimension") or "").strip().lower()
        if dimension == "service_type":
            dimension = "order_type"
        if dimension not in self.DIMENSIONS:
            raise ValidationError({"dimension": "Debe ser uno de: category, product, order_type, payment_method, modifier."})
        compare_mode = (request.query_params.get("compare") or request.query_params.get("compare_with") or "none").strip().lower()
        if compare_mode == "previous_week":
            compare_mode = "previous_period"
        if compare_mode not in {"none", "previous_period", "previous_year"}:
            raise ValidationError({"compare": "Debe ser none, previous_period, previous_week o previous_year."})

        start_dt, end_dt = _range_to_datetimes(start_date, end_date)
        base_qs = Payment.objects.select_related("order", "order__service_type", "payment_method", "reporting_payment_method").filter(
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        base_qs = _apply_common_filters(base_qs, request)
        payload = {
            "dimension": dimension,
            "items": self._breakdown(base_qs, dimension),
            "compare_items": [],
            "kpis": _kpis_for_queryset(base_qs),
            "compare_kpis": {"total": "0.00", "count": 0, "avg_ticket": "0.00"},
        }

        compare_range = _comparison_range(start_date, end_date, compare_mode, None)
        if compare_range:
            compare_start, compare_end = compare_range
            compare_start_dt, compare_end_dt = _range_to_datetimes(compare_start, compare_end)
            compare_qs = Payment.objects.select_related("order", "order__service_type", "payment_method", "reporting_payment_method").filter(
                created_at__gte=compare_start_dt,
                created_at__lte=compare_end_dt,
            )
            compare_qs = _apply_common_filters(compare_qs, request)
            payload["compare_items"] = self._breakdown(compare_qs, dimension)
            payload["compare_kpis"] = _kpis_for_queryset(compare_qs)
        return Response(payload)


class EmployeeWorkedHoursReportView(generics.GenericAPIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request, *args, **kwargs):
        start_date, end_date = _parse_report_dates(request)
        rows = (
            AttendanceRecord.objects.select_related("employee")
            .filter(
                date__gte=start_date,
                date__lte=end_date,
                employee__status="active",
                clock_in__isnull=False,
                clock_out__isnull=False,
            )
            .annotate(
                break_duration=Case(
                    When(
                        break_start__isnull=False,
                        break_end__isnull=False,
                        then=ExpressionWrapper(F("break_end") - F("break_start"), output_field=DurationField()),
                    ),
                    default=Value(timedelta(0)),
                    output_field=DurationField(),
                ),
                worked_duration=ExpressionWrapper(
                    F("clock_out") - F("clock_in") - F("break_duration"),
                    output_field=DurationField(),
                ),
            )
            .values("employee_id", "employee__full_name")
            .annotate(total_worked=Sum("worked_duration"))
            .order_by("employee__full_name")
        )

        payload = []
        total_minutes_all = 0
        for row in rows:
            seconds = int((row["total_worked"] or timedelta(0)).total_seconds())
            if seconds < 0:
                seconds = 0
            total_minutes_all += seconds // 60
            total_hours = (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            payload.append(
                {
                    "employee_id": row["employee_id"],
                    "employee_name": row["employee__full_name"],
                    "total_minutes": seconds // 60,
                    "total_hours": f"{total_hours:.2f}",
                }
            )

        return Response(
            {
                "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
                "employees": payload,
                "totals": {
                    "total_minutes": total_minutes_all,
                    "total_hours": f"{(Decimal(total_minutes_all) / Decimal(60)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}",
                },
            }
        )


class TransactionTicketView(generics.GenericAPIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request, payment_id: int):
        payment = Payment.objects.select_related("order").filter(pk=payment_id).first()
        if not payment:
            return Response({"detail": "Transacción no encontrada."}, status=404)
        payload = render_customer_ticket(payment.order)
        return Response(
            {
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "ticket_text": payload.get("text", ""),
                "ticket_html": payload.get("html", ""),
            }
        )


def _cycle_status(cycle: AttendanceCycle) -> str:
    if cycle.clock_in_at and not cycle.clock_out_at and not cycle.break_start_at:
        return "en_curso"
    if cycle.break_start_at and not cycle.break_end_at:
        return "break_en_curso"
    if cycle.clock_in_at and cycle.clock_out_at:
        return "completo"
    return "incompleto"


def _duration_minutes(start, end):
    return duration_seconds(start, end) // 60




def _cycle_break_minutes(cycle: AttendanceCycle):
    now = timezone.now()
    breaks = list(cycle.breaks.all()) if hasattr(cycle, "breaks") else []
    rows=[]
    for br in breaks:
        sec = duration_seconds(br.start_at, br.end_at or now)
        rows.append({"start_at": br.start_at, "end_at": br.end_at, "minutes": sec / 60, "seconds": sec})
    if not rows and cycle.break_start_at:
        sec = sum_cycle_break_seconds(cycle, include_open=True, now=now)
        rows=[{"start_at": cycle.break_start_at, "end_at": cycle.break_end_at, "minutes": sec / 60, "seconds": sec}]
    sec_total = cycle_break_seconds_for_reports(cycle)
    return sec_total / 60, rows, sec_total
class EmployeeHoursReportView(generics.GenericAPIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request):
        start_date, end_date = _parse_report_dates(request)
        employees = Employee.objects.select_related("user").filter(is_deleted=False).exclude(role="admin").exclude(full_name__istartswith="Empleado eliminado")
        records = AttendanceRecord.objects.select_related("employee").prefetch_related("cycles__breaks").filter(date__gte=start_date, date__lte=end_date, employee__in=employees)
        by_employee = {emp.id: {
                "employee_id": emp.id,
                "name": emp.full_name,
                "role": "Team Member" if str(emp.get_role_display()).lower() == "worker" else emp.get_role_display(),
                "days_worked": 0,
                "entries_count": 0,
                "exits_count": 0,
                "shift_minutes": 0,
                "break_minutes": 0,
                "net_minutes": 0,
                "current_state": "OFF_SHIFT",
                "last_clock_in_at": None,
                "status": emp.status,
            } for emp in employees}
        total_shift = total_break = total_net = 0
        for record in records:
            emp = record.employee
            row = by_employee[emp.id]
            shift = brk = 0
            entries = exits = 0
            for cycle in record.cycles.all():
                entries += 1 if cycle.clock_in_at else 0
                exits += 1 if cycle.clock_out_at else 0
                shift += _duration_minutes(cycle.clock_in_at, cycle.clock_out_at)
                brk += _cycle_break_minutes(cycle)[0]
            if entries:
                row["days_worked"] += 1
            row["entries_count"] += entries
            row["exits_count"] += exits
            row["shift_minutes"] += shift
            row["break_minutes"] += brk
            row["net_minutes"] += max(0, shift - brk)
            if record.clock_in and (not row["last_clock_in_at"] or record.clock_in > row["last_clock_in_at"]):
                row["last_clock_in_at"] = record.clock_in
            if record.clock_in and not record.clock_out:
                row["current_state"] = "ON_SHIFT"
            total_shift += shift
            total_break += brk
            total_net += max(0, shift - brk)

        return Response({
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "totals": {
                "employee_count": len(by_employee),
                "total_shift_minutes": total_shift,
                "total_break_minutes": total_break,
                "total_net_minutes": total_net,
                "total_hours": float((Decimal(total_net) / Decimal("60")).quantize(Decimal("0.01"))),
            },
            "employees": list(by_employee.values()),
        })


class EmployeeHoursDetailView(generics.GenericAPIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def get(self, request, employee_id: int):
        start_date, end_date = _parse_report_dates(request)
        employee = Employee.objects.filter(pk=employee_id, is_deleted=False).exclude(role="admin").exclude(full_name__istartswith="Empleado eliminado").first()
        if not employee:
            return Response({"detail": "Empleado no encontrado."}, status=404)
        tz = timezone.get_current_timezone()
        today_local = timezone.localdate()
        effective_end = min(end_date, today_local)
        if start_date > effective_end:
            return Response({
                "employee": {"id": employee.id, "name": employee.full_name, "role": employee.get_role_display()},
                "totals": {"shift_minutes": 0, "break_minutes": 0, "net_minutes": 0},
                "days": [],
            })
        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end_dt = timezone.make_aware(datetime.combine(effective_end, time.max), tz)
        cycles = AttendanceCycle.objects.select_related("attendance_record").prefetch_related("breaks").filter(
            attendance_record__employee=employee,
            clock_in_at__gte=start_dt,
            clock_in_at__lte=end_dt,
        ).order_by("clock_in_at", "id")
        day_map = {}
        current = start_date
        while current <= effective_end:
            day_map[current.isoformat()] = {"date": current.isoformat(), "daily_totals": {"shift_minutes": 0, "break_minutes": 0, "net_minutes": 0}, "cycles": []}
            current += timedelta(days=1)
        total_shift = total_break = total_net = 0
        for cycle in cycles:
            local_date = timezone.localtime(cycle.clock_in_at, tz).date()
            if local_date < start_date or local_date > end_date:
                continue
            key = local_date.isoformat()
            shift = _duration_minutes(cycle.clock_in_at, cycle.clock_out_at)
            brk, break_rows, brk_seconds = _cycle_break_minutes(cycle)
            net = max(0, shift - brk)
            total_shift += shift
            total_break += brk
            total_net += net
            day_map[key]["daily_totals"]["shift_minutes"] += shift
            day_map[key]["daily_totals"]["break_minutes"] += brk
            day_map[key]["daily_totals"]["net_minutes"] += net
            day_map[key]["cycles"].append({
                "clock_in_at": cycle.clock_in_at,
                "breaks_count": len(break_rows),
                "breaks": break_rows,
                "clock_out_at": cycle.clock_out_at,
                "shift_minutes": shift,
                "break_minutes": brk,
                "break_seconds": brk_seconds,
                "id": cycle.id,
                "break_seconds_override": cycle.break_seconds_override,
                "net_minutes": net,
                "status": _cycle_status(cycle),
                "clock_out_next_day": bool(cycle.clock_out_at and timezone.localtime(cycle.clock_out_at, tz).date() > local_date),
            })
        days = list(day_map.values())

        return Response({
            "employee": {"id": employee.id, "name": employee.full_name, "role": employee.get_role_display()},
            "totals": {"shift_minutes": total_shift, "break_minutes": total_break, "net_minutes": total_net},
            "days": days,
        })




def _parse_cycle_payload(data):
    cycle_date = parse_date(str(data.get("date") or ""))
    if not cycle_date:
        raise ValueError("Fecha es obligatoria.")
    clock_in_time = str(data.get("clock_in_time") or "").strip()
    if not clock_in_time:
        raise ValueError("La hora de entrada es obligatoria.")
    shift_seconds = data.get("shift_seconds")
    clock_out_time = data.get("clock_out_time")
    break_start_time = str(data.get("break_start_time") or "").strip()
    break_end_time = str(data.get("break_end_time") or "").strip()
    next_day = bool(data.get("clock_out_next_day"))
    break_seconds = int(data.get("break_seconds", data.get("break_seconds_override", 0)) or 0)
    if break_seconds < 0:
        raise ValueError("break_seconds no puede ser negativo.")

    ci_h, ci_m = [int(x) for x in clock_in_time.split(":")[:2]]
    tz = timezone.get_current_timezone()
    clock_in_at = timezone.make_aware(datetime.combine(cycle_date, time(ci_h, ci_m)), tz)

    clock_out_at = None
    if clock_out_time:
        co_h, co_m = [int(x) for x in str(clock_out_time).split(":")[:2]]
        clock_out_at = timezone.make_aware(datetime.combine(cycle_date, time(co_h, co_m)), tz)
        if next_day:
            clock_out_at += timedelta(days=1)
        elif clock_out_at < clock_in_at:
            raise ValueError("Salida no puede ser menor que entrada.")
    elif shift_seconds is not None and str(shift_seconds) != "":
        shift_seconds = int(shift_seconds)
        if shift_seconds < 0:
            raise ValueError("shift_seconds no puede ser negativo.")
        clock_out_at = clock_in_at + timedelta(seconds=shift_seconds)
    else:
        raise ValueError("clock_out_time o shift_seconds es obligatorio.")

    shift_seconds = duration_seconds(clock_in_at, clock_out_at)
    break_start_at = None
    break_end_at = None
    if bool(break_start_time) ^ bool(break_end_time):
        raise ValueError("Debes completar salida y regreso de break.")
    if break_start_time and break_end_time:
        bs_h, bs_m = [int(x) for x in break_start_time.split(":")[:2]]
        be_h, be_m = [int(x) for x in break_end_time.split(":")[:2]]
        break_start_at = timezone.make_aware(datetime.combine(cycle_date, time(bs_h, bs_m)), tz)
        break_end_at = timezone.make_aware(datetime.combine(cycle_date, time(be_h, be_m)), tz)
        if break_start_at < clock_in_at:
            break_start_at += timedelta(days=1)
        if break_end_at <= break_start_at:
            break_end_at += timedelta(days=1)
        if break_start_at < clock_in_at or break_end_at > clock_out_at:
            raise ValueError("El break debe estar dentro del turno.")
        break_seconds = duration_seconds(break_start_at, break_end_at)
    if break_seconds >= shift_seconds:
        raise ValueError("break_seconds no puede ser mayor o igual que duración del turno.")
    return cycle_date, clock_in_at, clock_out_at, break_seconds, break_start_at, break_end_at

class EmployeeHoursCycleCreateView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def post(self, request):
        if getattr(getattr(request.user, "profile", None), "role", "") != "admin":
            return Response({"detail": "Solo admin puede editar tarjetas de horas."}, status=status.HTTP_403_FORBIDDEN)
        employee_id = request.data.get("employee_id")
        employee = Employee.objects.filter(pk=employee_id).exclude(role="admin").first()
        if not employee:
            return Response({"detail": "Empleado no encontrado."}, status=404)
        try:
            cycle_date, clock_in_at, clock_out_at, break_seconds, break_start_at, break_end_at = _parse_cycle_payload(request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        logger.info("MANUAL_TIME_CARD_CREATE_START", extra={"employee_id": employee_id, "date": str(cycle_date), "has_break": bool(break_start_at and break_end_at)})
        reason = str(request.data.get("reason") or "Registro manual")
        if cycle_date > timezone.localdate():
            return Response({"detail": "No se pueden crear registros en fechas futuras."}, status=400)
        if AttendanceCycle.objects.filter(attendance_record__employee=employee, clock_out_at__isnull=True).exists():
            return Response({"detail": "Existe un turno abierto anterior. Cierra o edita ese turno antes de crear otro."}, status=400)
        record, _ = AttendanceRecord.objects.get_or_create(employee=employee, date=cycle_date)
        seq = (record.cycles.order_by("-sequence").values_list("sequence", flat=True).first() or 0) + 1
        cycle = AttendanceCycle.objects.create(
            attendance_record=record,
            sequence=seq,
            clock_in_at=clock_in_at,
            clock_out_at=clock_out_at,
            break_seconds_override=break_seconds,
            adjusted_by=request.user,
            adjusted_at=timezone.now(),
            adjustment_reason=reason,
        )
        shift_seconds = duration_seconds(clock_in_at, clock_out_at)
        breaks_payload = []
        if break_start_at and break_end_at:
            created_break = AttendanceBreak.objects.create(cycle=cycle, sequence=1, start_at=break_start_at, end_at=break_end_at)
            breaks_payload.append({"start_at": created_break.start_at, "end_at": created_break.end_at, "seconds": duration_seconds(created_break.start_at, created_break.end_at)})
            logger.info("MANUAL_TIME_CARD_BREAK_CREATED", extra={"cycle_id": cycle.id, "break_id": created_break.id, "break_seconds": breaks_payload[0]["seconds"]})
        AttendanceCycleAdjustment.objects.create(cycle=cycle, employee=employee, changed_by=request.user, new_clock_in_at=clock_in_at, new_clock_out_at=clock_out_at, new_break_seconds_override=break_seconds, old_computed_break_seconds=0, new_break_seconds=break_seconds, reason=reason)
        net_seconds = max(0, shift_seconds-break_seconds)
        logger.info("MANUAL_TIME_CARD_CREATE_RESULT", extra={"cycle_id": cycle.id, "shift_seconds": shift_seconds, "break_seconds": break_seconds, "net_seconds": net_seconds})
        return Response({"ok": True, "cycle": {"id": cycle.id, "employee_id": employee.id, "date": cycle_date, "clock_in_at": cycle.clock_in_at, "clock_out_at": cycle.clock_out_at, "shift_seconds": shift_seconds, "break_seconds": break_seconds, "net_seconds": net_seconds, "breaks_count": len(breaks_payload), "breaks": breaks_payload, "adjusted": True, "created_manually": True}})


class EmployeeHoursCycleUpdateView(APIView):
    permission_classes = [IsCashierOrManagerOrAdmin]

    def patch(self, request, cycle_id: int):
        if getattr(getattr(request.user, "profile", None), "role", "") != "admin":
            return Response({"detail": "Solo admin puede editar tarjetas de horas."}, status=status.HTTP_403_FORBIDDEN)
        cycle = AttendanceCycle.objects.select_related("attendance_record__employee").filter(pk=cycle_id).first()
        if not cycle:
            return Response({"detail": "Ciclo no encontrado."}, status=404)
        old_ci, old_co, old_override = cycle.clock_in_at, cycle.clock_out_at, cycle.break_seconds_override
        old_computed = sum_cycle_break_seconds(cycle, include_open=False)
        reason = str(request.data.get("reason") or "Corrección manual")
        try:
            cycle_date, clock_in_at, clock_out_at, break_seconds, break_start_at, break_end_at = _parse_cycle_payload(request.data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        cycle.attendance_record.date = cycle_date
        cycle.attendance_record.save(update_fields=["date"])
        cycle.clock_in_at = clock_in_at
        cycle.clock_out_at = clock_out_at
        cycle.break_seconds_override = break_seconds
        cycle.adjusted_by = request.user
        cycle.adjusted_at = timezone.now()
        cycle.adjustment_reason = reason
        cycle.save()
        new_break = cycle_break_seconds_for_reports(cycle)
        AttendanceCycleAdjustment.objects.create(cycle=cycle, employee=cycle.attendance_record.employee, changed_by=request.user, old_clock_in_at=old_ci, new_clock_in_at=cycle.clock_in_at, old_clock_out_at=old_co, new_clock_out_at=cycle.clock_out_at, old_break_seconds_override=old_override, new_break_seconds_override=cycle.break_seconds_override, old_computed_break_seconds=old_computed, new_break_seconds=new_break, reason=reason)
        shift_seconds = duration_seconds(cycle.clock_in_at, cycle.clock_out_at)
        return Response({"ok": True, "cycle": {"id": cycle.id, "date": cycle.attendance_record.date, "clock_in_at": cycle.clock_in_at, "clock_out_at": cycle.clock_out_at, "shift_seconds": shift_seconds, "break_seconds": new_break, "net_seconds": max(0, shift_seconds-new_break), "break_seconds_override": cycle.break_seconds_override, "adjusted": cycle.break_seconds_override is not None}})
