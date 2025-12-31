from decimal import Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from rest_framework import serializers
from apps.cashier.models import Register, CashSession, CloseoutCount
from apps.orders.models import Order
from apps.payments.models import Payment, Refund


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Register
        fields = ["id", "name", "branch", "is_active", "created_at"]


class CashSessionSerializer(serializers.ModelSerializer):
    register_name = serializers.CharField(source="register.name", read_only=True)
    branch_id = serializers.IntegerField(source="register.branch_id", read_only=True)
    opened_by_username = serializers.CharField(source="opened_by.username", read_only=True)

    class Meta:
        model = CashSession
        fields = [
            "id",
            "register",
            "register_name",
            "branch_id",
            "opened_by",
            "opened_by_username",
            "opened_at",
            "opening_cash",
            "status",
            "closed_by",
            "closed_at",
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


class CashSessionSummarySerializer(serializers.Serializer):
    expected_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    expected_card = serializers.DecimalField(max_digits=10, decimal_places=2)
    expected_transfer = serializers.DecimalField(max_digits=10, decimal_places=2)
    expected_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    expected_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    refunds_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    refunds_card = serializers.DecimalField(max_digits=10, decimal_places=2)
    refunds_transfer = serializers.DecimalField(max_digits=10, decimal_places=2)
    refunds_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    refunds_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    net_sales_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    counted_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    counted_card = serializers.DecimalField(max_digits=10, decimal_places=2)
    counted_transfer = serializers.DecimalField(max_digits=10, decimal_places=2)
    counted_tips = serializers.DecimalField(max_digits=10, decimal_places=2)
    over_short_cash = serializers.DecimalField(max_digits=10, decimal_places=2)
    over_short_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    orders_count = serializers.IntegerField()
    gross_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    subtotal_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    tax_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    discount_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    tips_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    cash_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    card_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    transfer_total = serializers.DecimalField(max_digits=10, decimal_places=2)


def calculate_shift_summary(session: CashSession) -> dict:
    payments = Payment.objects.filter(cash_session=session)
    payment_totals = payments.aggregate(
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
        tips_total=Sum("tip_amount"),
        expected_total=Sum(
            ExpressionWrapper(
                F("amount") + F("tip_amount"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        ),
    )
    refunds = Refund.objects.filter(cash_session=session)
    refund_totals = refunds.aggregate(
        refunds_cash=Sum(
            ExpressionWrapper(
                F("amount") + F("tip_refunded"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            filter=Q(method="cash"),
        ),
        refunds_card=Sum(
            ExpressionWrapper(
                F("amount") + F("tip_refunded"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            filter=Q(method="card"),
        ),
        refunds_transfer=Sum(
            ExpressionWrapper(
                F("amount") + F("tip_refunded"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            filter=Q(method="transfer"),
        ),
        refunds_tips=Sum("tip_refunded"),
        refunds_total=Sum(
            ExpressionWrapper(
                F("amount") + F("tip_refunded"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        ),
        refunds_sales=Sum("amount"),
    )

    order_ids = payments.values_list("order_id", flat=True).distinct()
    orders = Order.objects.filter(id__in=order_ids)
    order_totals = orders.aggregate(
        gross_total=Sum("total"),
        subtotal_total=Sum("subtotal"),
        tax_total=Sum("tax"),
        discount_total=Sum("discount_total"),
    )

    closeout = getattr(session, "closeout", None)
    counted_cash = closeout.counted_cash if closeout else Decimal("0")
    counted_card = closeout.counted_card if closeout else Decimal("0")
    counted_transfer = closeout.counted_transfer if closeout else Decimal("0")
    counted_tips = closeout.counted_tips if closeout else Decimal("0")

    refunds_cash = refund_totals["refunds_cash"] or Decimal("0")
    refunds_card = refund_totals["refunds_card"] or Decimal("0")
    refunds_transfer = refund_totals["refunds_transfer"] or Decimal("0")
    refunds_tips = refund_totals["refunds_tips"] or Decimal("0")
    refunds_total = refund_totals["refunds_total"] or Decimal("0")
    refunds_sales = refund_totals["refunds_sales"] or Decimal("0")

    expected_cash = (payment_totals["cash_total"] or Decimal("0")) - refunds_cash
    expected_card = (payment_totals["card_total"] or Decimal("0")) - refunds_card
    expected_transfer = (payment_totals["transfer_total"] or Decimal("0")) - refunds_transfer
    expected_tips = (payment_totals["tips_total"] or Decimal("0")) - refunds_tips
    expected_total = (payment_totals["expected_total"] or Decimal("0")) - refunds_total

    over_short_cash = counted_cash - expected_cash
    over_short_total = (counted_cash + counted_card + counted_transfer + counted_tips) - (
        expected_cash + expected_card + expected_transfer + expected_tips
    )

    return {
        "expected_cash": expected_cash,
        "expected_card": expected_card,
        "expected_transfer": expected_transfer,
        "expected_tips": expected_tips,
        "expected_total": expected_total,
        "refunds_cash": refunds_cash,
        "refunds_card": refunds_card,
        "refunds_transfer": refunds_transfer,
        "refunds_tips": refunds_tips,
        "refunds_total": refunds_total,
        "net_sales_total": (order_totals["gross_total"] or Decimal("0")) - refunds_sales,
        "counted_cash": counted_cash,
        "counted_card": counted_card,
        "counted_transfer": counted_transfer,
        "counted_tips": counted_tips,
        "over_short_cash": over_short_cash,
        "over_short_total": over_short_total,
        "orders_count": orders.count(),
        "gross_total": order_totals["gross_total"] or Decimal("0"),
        "subtotal_total": order_totals["subtotal_total"] or Decimal("0"),
        "tax_total": order_totals["tax_total"] or Decimal("0"),
        "discount_total": order_totals["discount_total"] or Decimal("0"),
        "tips_total": expected_tips,
        "cash_total": expected_cash,
        "card_total": expected_card,
        "transfer_total": expected_transfer,
    }
