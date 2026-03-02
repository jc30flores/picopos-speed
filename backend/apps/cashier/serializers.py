from decimal import Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum, Count
from rest_framework import serializers
from apps.cashier.models import Register, CashSession, CloseoutCount, CashTransaction
from apps.orders.models import Order
from apps.payments.models import Payment


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
        ]
        read_only_fields = ["status", "closed_by", "closed_at"]


class CloseoutCountSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloseoutCount
        fields = [
            "id",
            "cash_session",
            "counted_cash",
            "counted_card",
            "counted_transfer",
            "counted_tips",
            "notes",
        ]


class CashTransactionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = CashTransaction
        fields = ["id", "session", "type", "amount", "description", "created_by", "created_by_username", "created_at"]
        read_only_fields = ["session", "created_by", "created_at"]


class CashSessionSummarySerializer(serializers.Serializer):
    opening_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cash_sales = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cash_out = serializers.DecimalField(max_digits=10, decimal_places=2)
    expected_cash_in_drawer = serializers.DecimalField(max_digits=10, decimal_places=2)
    counted_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    over_short_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    methods = serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=2))
    payment_counts = serializers.DictField(child=serializers.IntegerField())
    orders_count = serializers.IntegerField()


def calculate_shift_summary(session: CashSession) -> dict:
    end = session.closed_at
    payments = Payment.objects.filter(created_at__gte=session.opened_at)
    if end:
        payments = payments.filter(created_at__lte=end)

    payment_totals = payments.aggregate(
        cash_total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2)), filter=Q(method="cash")),
        card_total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2)), filter=Q(method="card")),
        transfer_total=Sum(ExpressionWrapper(F("amount") + F("tip_amount"), output_field=DecimalField(max_digits=10, decimal_places=2)), filter=Q(method="transfer")),
        cash_count=Count("id", filter=Q(method="cash")),
        card_count=Count("id", filter=Q(method="card")),
        transfer_count=Count("id", filter=Q(method="transfer")),
    )

    transactions = CashTransaction.objects.filter(session=session)
    total_cash_out = transactions.filter(type__in=["cash_out", "expense", "payout"]).aggregate(total=Sum("amount")).get("total") or Decimal("0")
    total_cash_in = transactions.filter(type="cash_in").aggregate(total=Sum("amount")).get("total") or Decimal("0")

    total_cash_sales = payment_totals["cash_total"] or Decimal("0")
    expected_cash_in_drawer = session.opening_cash + total_cash_sales + total_cash_in - total_cash_out
    counted_cash = session.closing_counted_cash if session.closing_counted_cash is not None else Decimal("0")
    over_short_cash = counted_cash - expected_cash_in_drawer

    order_ids = payments.values_list("order_id", flat=True).distinct()

    return {
        "opening_cash": session.opening_cash,
        "total_cash_sales": total_cash_sales,
        "total_cash_out": total_cash_out,
        "expected_cash_in_drawer": expected_cash_in_drawer,
        "counted_cash": counted_cash,
        "over_short_cash": over_short_cash,
        "methods": {
            "cash": total_cash_sales,
            "card": payment_totals["card_total"] or Decimal("0"),
            "transfer": payment_totals["transfer_total"] or Decimal("0"),
            "cash_in": total_cash_in,
        },
        "payment_counts": {
            "cash": payment_totals["cash_count"] or 0,
            "card": payment_totals["card_count"] or 0,
            "transfer": payment_totals["transfer_count"] or 0,
        },
        "orders_count": Order.objects.filter(id__in=order_ids).count(),
    }
