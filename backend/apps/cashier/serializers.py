from decimal import Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Count
from rest_framework import serializers
from apps.cashier.models import Register, CashSession, CloseoutCount, CashTransaction
from apps.orders.models import Order
from apps.payments.models import Payment


PAYMENT_METHOD_CODES = ["CASH", "CARD", "TRANSFER", "PEDIDOS_YA", "PAYPAL"]


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Register
        fields = ["id", "name", "station_name", "branch", "is_active", "created_at"]


class CashSessionSerializer(serializers.ModelSerializer):
    register_name = serializers.CharField(source="register.name", read_only=True)
    station_name = serializers.CharField(source="register.station_name", read_only=True)
    branch_id = serializers.IntegerField(source="register.branch_id", read_only=True)
    opened_by_username = serializers.CharField(source="opened_by.username", read_only=True)
    closed_by_username = serializers.CharField(source="closed_by.username", read_only=True)

    class Meta:
        model = CashSession
        fields = [
            "id",
            "register",
            "register_name",
            "station_name",
            "branch_id",
            "opened_by",
            "opened_by_username",
            "opened_at",
            "opening_cash",
            "status",
            "closed_by",
            "closed_by_username",
            "closed_at",
            "closing_counted_cash",
            "notes",
            "summary_snapshot",
        ]
        read_only_fields = ["status", "closed_by", "closed_at", "summary_snapshot"]


class CloseoutCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloseoutCount
        fields = ["id", "cash_session", "counted_cash", "counted_card", "counted_transfer", "counted_tips", "notes"]


class CashTransactionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    display_type = serializers.SerializerMethodField()
    impacts_cash = serializers.SerializerMethodField()

    class Meta:
        model = CashTransaction
        fields = ["id", "session", "type", "display_type", "impacts_cash", "amount", "description", "created_by", "created_by_username", "created_at"]
        read_only_fields = ["session", "created_by", "created_at"]

    def get_display_type(self, obj: CashTransaction) -> str:
        mapping = {
            "cash_in": "EFECTIVO",
            "cash_out": "EFECTIVO",
            "card": "TARJETA",
            "transfer": "TRANSFERENCIA",
            "pedidosya": "PEDIDOSYA",
            "paypal": "PAYPAL",
        }
        return mapping.get(obj.type, obj.type.upper())

    def get_impacts_cash(self, obj: CashTransaction) -> bool:
        return obj.type in {"cash_in", "cash_out", "expense", "payout"}


class CashSessionSummarySerializer(serializers.Serializer):
    opening_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cash_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    cash_expenses_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    expected_cash_in_drawer = serializers.DecimalField(max_digits=10, decimal_places=2)
    counted_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    difference = serializers.DecimalField(max_digits=10, decimal_places=2)
    methods = serializers.DictField()
    orders_count = serializers.IntegerField()


def _method_code_expr():
    # prefer FK method code, fallback to legacy char method
    return None


def calculate_shift_summary(session: CashSession) -> dict:
    if session.status == "closed" and session.summary_snapshot:
        return session.summary_snapshot

    end = session.closed_at
    payments = Payment.objects.filter(created_at__gte=session.opened_at)
    if end:
        payments = payments.filter(created_at__lte=end)

    methods: dict[str, dict[str, Decimal | int]] = {}
    for code in PAYMENT_METHOD_CODES:
        q = Q(payment_method__code=code)
        if code == "CASH":
            q = q | Q(payment_method__isnull=True, method="cash")
        elif code == "CARD":
            q = q | Q(payment_method__isnull=True, method="card")
        elif code == "TRANSFER":
            q = q | Q(payment_method__isnull=True, method="transfer")
        total = payments.aggregate(v=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2)), filter=q))["v"] or Decimal("0")
        count = payments.aggregate(c=Count("id", filter=q))["c"] or 0
        methods[code] = {"count": int(count), "total": total}

    transactions = CashTransaction.objects.filter(session=session)
    cash_expenses_total = transactions.filter(type__in=["cash_out", "expense", "payout"]).aggregate(total=Sum("amount")).get("total") or Decimal("0")
    cash_in_total = transactions.filter(type="cash_in").aggregate(total=Sum("amount")).get("total") or Decimal("0")

    total_cash_sales = methods["CASH"]["total"]
    expected_cash_in_drawer = session.opening_cash + cash_in_total - cash_expenses_total
    counted_cash = session.closing_counted_cash if session.closing_counted_cash is not None else Decimal("0")
    difference = counted_cash - expected_cash_in_drawer
    order_ids = payments.values_list("order_id", flat=True).distinct()

    return {
        "opening_cash": session.opening_cash,
        "total_cash_sales": total_cash_sales,
        "cash_expenses_total": cash_expenses_total,
        "cash_in_total": cash_in_total,
        "expected_cash_in_drawer": expected_cash_in_drawer,
        "counted_cash": counted_cash,
        "difference": difference,
        "methods": methods,
        "orders_count": Order.objects.filter(id__in=order_ids).count(),
    }
