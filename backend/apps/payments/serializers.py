from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework import serializers
from apps.orders.models import Order
from apps.payments.models import Payment, Refund, PaymentMethod
from apps.payments.normalization import normalize_payment_method_code

logger = logging.getLogger(__name__)


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ["id", "code", "name", "is_cash", "sort_order", "is_active"]


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=6)
    amount_applied = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, write_only=True)
    tip_amount = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, default=Decimal("0"))
    cash_received = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, allow_null=True)
    received_by = serializers.CharField(source="received_by.username", read_only=True)
    payment_method_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    card_type = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "method",
            "payment_method",
            "payment_method_code",
            "payment_method_name",
            "amount",
            "amount_applied",
            "cash_received",
            "tip_amount",
            "card_type",
            "reference",
            "received_by",
            "created_at",
        ]

    def validate(self, attrs):
        order = attrs.get("order")
        raw_amount_applied = attrs.pop("amount_applied", None)
        raw_amount = raw_amount_applied if raw_amount_applied is not None else attrs.get("amount")
        amount = self._normalize_money(raw_amount, field="amount")
        tip_amount = self._normalize_money(attrs.get("tip_amount") or Decimal("0"), field="tip_amount")
        attrs["amount"] = amount
        attrs["tip_amount"] = tip_amount
        if attrs.get("cash_received") is not None:
            attrs["cash_received"] = self._normalize_money(attrs.get("cash_received"), field="cash_received")

        code = normalize_payment_method_code(attrs.pop("payment_method_code", ""))
        payment_method = attrs.get("payment_method")
        if code and not payment_method:
            payment_method = PaymentMethod.objects.filter(code__iexact=code, is_active=True).first()
            if not payment_method:
                raise serializers.ValidationError("Payment method not found")
            attrs["payment_method"] = payment_method

        if payment_method and not attrs.get("method"):
            method_code = payment_method.code.lower()
            if method_code == "cash":
                attrs["method"] = "cash"
            elif method_code in {"card_debit", "card_credit", "card"}:
                attrs["method"] = "card"
            else:
                attrs["method"] = "transfer"
            if method_code == "card_debit":
                attrs["card_type"] = "debit"
            elif method_code in {"card_credit", "card"} and not attrs.get("card_type"):
                attrs["card_type"] = "credit"

        method_value = (attrs.get("method") or "").strip().lower()
        card_type = (attrs.get("card_type") or "").strip().lower()
        if method_value == "card":
            if card_type not in {"debit", "credit"}:
                raise serializers.ValidationError({"card_type": "Debe seleccionar tipo de tarjeta: débito o crédito."})
            attrs["card_type"] = card_type
        else:
            attrs["card_type"] = ""

        if amount <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        if tip_amount < 0:
            raise serializers.ValidationError("Tip amount cannot be negative")

        if order is None:
            raise serializers.ValidationError("Order is required")
        if order.financial_status == "voided":
            raise serializers.ValidationError("Voided orders cannot accept payments")

        remaining = self._remaining_balance(order)
        if remaining <= 0:
            raise serializers.ValidationError("Order is already paid")
        diff = (amount - remaining).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        logger.info(
            "payment.validation.balance_check order_id=%s remaining_balance=%s amount_request=%s diff=%s",
            getattr(order, "id", None),
            remaining,
            amount,
            diff,
        )
        if diff > Decimal("0.01"):
            logger.warning(
                "payment.validation.exceeds_remaining order_id=%s remaining=%s amount=%s diff=%s",
                getattr(order, "id", None),
                remaining,
                amount,
                diff,
            )
            raise serializers.ValidationError("Payment exceeds remaining balance")

        return attrs

    def _normalize_money(self, value: Decimal | str | float | None, *, field: str) -> Decimal:
        try:
            normalized = Decimal(str(value if value is not None else "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError, TypeError):
            raise serializers.ValidationError({field: "Monto inválido"})
        digits = normalized.as_tuple().digits
        integer_digits = len(digits) - 2
        if integer_digits > 8:
            raise serializers.ValidationError({field: "El monto excede el máximo permitido"})
        return normalized

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["received_by"] = request.user
        return super().create(validated_data)

    def _remaining_balance(self, order: Order) -> Decimal:
        paid = Payment.objects.filter(order=order).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0")
        return (order.total - paid).quantize(Decimal("0.01"))


class RefundSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(source="created_by.username", read_only=True)
    approved_by = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "order",
            "original_payment",
            "cash_session",
            "method",
            "payment_method",
            "amount",
            "tip_refunded",
            "reason",
            "approved_by",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["cash_session", "approved_by", "created_by", "created_at"]

    def validate(self, attrs):
        order = attrs.get("order")
        original_payment = attrs.get("original_payment")
        amount = attrs.get("amount") or Decimal("0")
        tip_refunded = attrs.get("tip_refunded") or Decimal("0")
        reason = (attrs.get("reason") or "").strip()

        if order is None:
            raise serializers.ValidationError("Order is required")
        if order.financial_status == "voided":
            raise serializers.ValidationError("Voided orders cannot be refunded")
        if amount <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        if tip_refunded < 0:
            raise serializers.ValidationError("Tip refund cannot be negative")
        if not reason:
            raise serializers.ValidationError("Reason is required")

        refund_total = amount + tip_refunded
        total_paid = Payment.objects.filter(order=order).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0")
        total_refunded = Refund.objects.filter(order=order).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )["total"] or Decimal("0")

        if total_paid <= 0:
            raise serializers.ValidationError("Order has no payments to refund")
        if refund_total + total_refunded > total_paid:
            raise serializers.ValidationError("Refund exceeds refundable amount")

        if original_payment:
            if original_payment.order_id != order.id:
                raise serializers.ValidationError("Payment does not belong to this order")
            payment_total = original_payment.amount + original_payment.tip_amount
            payment_refunded = Refund.objects.filter(original_payment=original_payment).aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("amount") + F("tip_refunded"),
                        output_field=DecimalField(max_digits=10, decimal_places=2),
                    )
                )
            )["total"] or Decimal("0")
            if refund_total + payment_refunded > payment_total:
                raise serializers.ValidationError("Refund exceeds original payment amount")

        return attrs
