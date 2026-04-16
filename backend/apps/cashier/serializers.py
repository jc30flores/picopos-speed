from decimal import Decimal, ROUND_HALF_UP

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from rest_framework import serializers

from apps.cashier.models import Register, CashSession, CloseoutCount, CashTransaction
from apps.cashier.services.reconciliation import calculate_session_payment_method_net
from apps.orders.models import Order
from apps.payments.models import Payment

MONEY_Q = Decimal("0.01")

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
            "closing_total_bills",
            "closing_total_coins",
            "closing_total_pos_cards",
            "closing_total_pedidos_ya",
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
            "expense": "EFECTIVO",
            "payout": "EFECTIVO",
            "card": "TARJETA",
            "transfer": "TRANSFERENCIA",
            "pedidosya": "PEDIDOSYA",
            "paypal": "PAYPAL",
        }
        return mapping.get(obj.type, obj.type.upper())

    def get_impacts_cash(self, obj: CashTransaction) -> bool:
        return obj.type in {"cash_in", "cash_out", "expense", "payout"}


class CashSessionSummarySerializer(serializers.Serializer):
    opening_cash = serializers.CharField()
    total_cash_sales = serializers.CharField()
    cash_expenses_total = serializers.CharField()
    expected_cash_in_drawer = serializers.CharField()
    counted_cash = serializers.CharField()
    difference = serializers.CharField()
    totals_by_method = serializers.DictField()
    cash_movements = serializers.ListField()
    non_cash_sales = serializers.ListField()
    orders_count = serializers.IntegerField()


class CashSessionCloseSerializer(serializers.Serializer):
    total_billetes = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    total_monedas = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    total_pos_tarjetas = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=Decimal("0"))
    total_pedidos_ya = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=Decimal("0"))
    total_contado = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        total_billetes = _q2(attrs.get("total_billetes"))
        total_monedas = _q2(attrs.get("total_monedas"))
        total_pos_tarjetas = _q2(attrs.get("total_pos_tarjetas"))
        total_pedidos_ya = _q2(attrs.get("total_pedidos_ya"))
        total_contado = attrs.get("total_contado")

        if total_billetes < 0 or total_monedas < 0 or total_pos_tarjetas < 0 or total_pedidos_ya < 0:
            raise serializers.ValidationError("Los totales de cierre deben ser montos no negativos.")

        computed_total = _q2(total_billetes + total_monedas)
        if total_contado is None:
            attrs["total_contado"] = computed_total
        else:
            total_contado = _q2(total_contado)
            if total_contado < 0:
                raise serializers.ValidationError("El total contado debe ser un monto no negativo.")
            if abs(total_contado - computed_total) > MONEY_Q:
                raise serializers.ValidationError("El total contado no coincide con billetes + monedas.")
            attrs["total_contado"] = total_contado

        attrs["total_billetes"] = total_billetes
        attrs["total_monedas"] = total_monedas
        attrs["total_pos_tarjetas"] = total_pos_tarjetas
        attrs["total_pedidos_ya"] = total_pedidos_ya
        attrs["notes"] = str(attrs.get("notes", "")).strip()
        return attrs


def _q2(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def calculate_shift_summary(session: CashSession) -> dict:
    if session.status == "closed" and session.summary_snapshot:
        return session.summary_snapshot

    payment_net = calculate_session_payment_method_net(session)
    totals_by_method = payment_net.totals_by_method
    non_cash_sales = payment_net.non_cash_movements

    transactions = CashTransaction.objects.filter(session=session).order_by("-created_at")
    expense_transactions = transactions.filter(
        type__in=["cash_out", "expense", "payout"],
        payment__isnull=True,
        refund__isnull=True,
    )
    cash_movements = [
        {
            "id": tx.id,
            "type": tx.type,
            "description": tx.description,
            "amount": f"{-_q2(tx.amount):.2f}",
            "created_at": tx.created_at.isoformat(),
        }
        for tx in expense_transactions
    ]

    expenses_total = _q2(expense_transactions.aggregate(total=Sum("amount")).get("total"))

    cash_initial = _q2(session.opening_cash)
    cash_sales = _q2(totals_by_method.get("cash"))
    expected_cash_in_drawer = _q2(cash_initial + cash_sales - expenses_total)
    counted_cash = _q2(session.closing_counted_cash if session.closing_counted_cash is not None else Decimal("0"))
    counted_bills = _q2(session.closing_total_bills if session.closing_total_bills is not None else Decimal("0"))
    counted_coins = _q2(session.closing_total_coins if session.closing_total_coins is not None else Decimal("0"))
    counted_pos_cards = _q2(session.closing_total_pos_cards if session.closing_total_pos_cards is not None else Decimal("0"))
    counted_pedidos_ya = _q2(session.closing_total_pedidos_ya if session.closing_total_pedidos_ya is not None else Decimal("0"))
    difference = _q2(counted_cash - expected_cash_in_drawer)
    payments = Payment.objects.filter(cash_session=session)
    order_ids = payments.values_list("order_id", flat=True).distinct()

    return {
        "opening_cash": f"{cash_initial:.2f}",
        "total_cash_sales": f"{cash_sales:.2f}",
        "cash_expenses_total": f"{expenses_total:.2f}",
        "expected_cash_in_drawer": f"{expected_cash_in_drawer:.2f}",
        "counted_cash": f"{counted_cash:.2f}",
        "counted_bills": f"{counted_bills:.2f}",
        "counted_coins": f"{counted_coins:.2f}",
        "counted_pos_cards": f"{counted_pos_cards:.2f}",
        "counted_pedidos_ya": f"{counted_pedidos_ya:.2f}",
        "difference": f"{difference:.2f}",
        "totals_by_method": {k: f"{_q2(v):.2f}" for k, v in totals_by_method.items()},
        "method_labels": payment_net.labels_by_method,
        "cash_movements": cash_movements,
        "non_cash_sales": non_cash_sales,
        "orders_count": Order.objects.filter(id__in=order_ids).count(),
    }
