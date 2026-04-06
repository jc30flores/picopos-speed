from calendar import monthrange
from datetime import datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Case, CharField, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDay, TruncHour, TruncMonth, TruncWeek, TruncYear
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.models import ServiceType
from apps.core.permissions import IsCashierOrManagerOrAdmin
from apps.core.service_types import SERVICE_TYPE_LABELS, normalize_service_type
from apps.orders.models import OrderItem, OrderItemModifier
from apps.payments.models import Payment, Refund
from apps.payments.normalization import PAYMENT_METHOD_LABELS, payment_code_from_payment
from apps.reports.serializers import SalesReportSerializer

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
        When(reporting_payment_method__code__iexact="card", card_type__iexact="debit", then=Value("card_debit")),
        When(reporting_payment_method__code__iexact="card", then=Value("card_credit")),
        When(reporting_payment_method__code__iexact="credit_card", then=Value("card_credit")),
        When(reporting_payment_method__code__iexact="debit_card", then=Value("card_debit")),
        When(reporting_payment_method__code__iexact="efectivo", then=Value("cash")),
        When(reporting_payment_method__code__iexact="01", then=Value("cash")),
        When(reporting_payment_method__code__iexact="pedidosya", then=Value("pedidos_ya")),
        When(reporting_payment_method__isnull=False, then=F("reporting_payment_method__code")),
        When(payment_method__code__iexact="card", card_type__iexact="debit", then=Value("card_debit")),
        When(payment_method__code__iexact="card", then=Value("card_credit")),
        When(payment_method__code__iexact="credit_card", then=Value("card_credit")),
        When(payment_method__code__iexact="debit_card", then=Value("card_debit")),
        When(payment_method__code__iexact="efectivo", then=Value("cash")),
        When(payment_method__code__iexact="01", then=Value("cash")),
        When(payment_method__code__iexact="pedidosya", then=Value("pedidos_ya")),
        When(payment_method__isnull=False, then=F("payment_method__code")),
        When(method__iexact="cash", then=Value("cash")),
        When(method__iexact="card", card_type__iexact="debit", then=Value("card_debit")),
        When(method__iexact="card", then=Value("card_credit")),
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
        queryset = _apply_common_filters(queryset, self.request)
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
