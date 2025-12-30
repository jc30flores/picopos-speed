from decimal import Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework import serializers
from apps.orders.models import Order
from apps.payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    received_by = serializers.CharField(source="received_by.username", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order",
            "method",
            "amount",
            "tip_amount",
            "reference",
            "received_by",
            "created_at",
        ]

    def validate(self, attrs):
        order = attrs.get("order")
        amount = attrs.get("amount") or Decimal("0")
        tip_amount = attrs.get("tip_amount") or Decimal("0")

        if amount <= 0:
            raise serializers.ValidationError("Amount must be greater than 0")
        if tip_amount < 0:
            raise serializers.ValidationError("Tip amount cannot be negative")

        if order is None:
            raise serializers.ValidationError("Order is required")

        remaining = self._remaining_balance(order)
        total_payment = amount + tip_amount
        if remaining <= 0:
            raise serializers.ValidationError("Order is already paid")
        if total_payment > remaining:
            raise serializers.ValidationError("Payment exceeds remaining balance")

        return attrs

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
