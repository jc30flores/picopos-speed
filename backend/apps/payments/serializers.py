from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
import re
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from rest_framework import serializers
from apps.orders.models import Order
from apps.payments.models import Payment, Refund, PaymentMethod
from apps.core.models import ServiceType
from apps.payments.normalization import normalize_payment_method_code, resolve_payment_method

logger = logging.getLogger(__name__)


class PaymentMethodSerializer(serializers.ModelSerializer):
    color = serializers.CharField(source="color_hex", required=False, allow_blank=True)
    order = serializers.IntegerField(source="sort_order", required=False)
    active = serializers.BooleanField(source="is_active", required=False)
    linked_order_type = serializers.PrimaryKeyRelatedField(
        source="auto_select_order_type",
        queryset=ServiceType.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    linked_order_type_id = serializers.PrimaryKeyRelatedField(
        source="auto_select_order_type",
        queryset=ServiceType.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    linked_order_type_name = serializers.CharField(source="auto_select_order_type.label", read_only=True)

    class Meta:
        model = PaymentMethod
        fields = [
            "id",
            "code",
            "name",
            "is_cash",
            "sort_order",
            "is_active",
            "active",
            "color_hex",
            "color",
            "order",
            "is_default",
            "fiscal_payment_type",
            "linked_order_type_id",
            "linked_order_type",
            "linked_order_type_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "linked_order_type_name"]

    def validate_color(self, value: str | None) -> str:
        return self.validate_color_hex(value)

    def validate_color_hex(self, value: str | None) -> str:
        cleaned = (value or "").strip().upper()
        if not cleaned:
            return ""
        if not re.fullmatch(r"#[0-9A-F]{6}", cleaned):
            raise serializers.ValidationError("Color HEX inválido. Usa formato #RRGGBB.")
        return cleaned

    def validate_code(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Z0-9_]+", "_", (value or "").upper()).strip("_").lower()
        if not cleaned:
            raise serializers.ValidationError("Código requerido.")
        qs = PaymentMethod.objects.filter(code__iexact=cleaned)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un método con este código.")
        return cleaned

    def validate_name(self, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise serializers.ValidationError("Nombre requerido.")
        qs = PaymentMethod.objects.filter(name__iexact=cleaned, is_active=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        incoming_active = self.initial_data.get("is_active", self.initial_data.get("active", getattr(self.instance, "is_active", True)))
        if self._as_bool(incoming_active, True) and qs.exists():
            raise serializers.ValidationError("Ya existe un método activo con este nombre.")
        return cleaned

    def validate_fiscal_payment_type(self, value: str) -> str:
        cleaned = str(value or "").strip().upper()
        allowed = {choice[0] for choice in PaymentMethod.FISCAL_PAYMENT_TYPE_CHOICES}
        if cleaned not in allowed:
            raise serializers.ValidationError("Categoría fiscal inválida. Usa CASH, CARD o TRANSFER.")
        return cleaned

    @staticmethod
    def _as_bool(value, default=False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "si", "sí"}

    def validate(self, attrs):
        is_default = self._as_bool(attrs.get("is_default", getattr(self.instance, "is_default", False)))
        is_active = self._as_bool(attrs.get("is_active", getattr(self.instance, "is_active", True)))
        fiscal_type = attrs.get("fiscal_payment_type", getattr(self.instance, "fiscal_payment_type", PaymentMethod.FISCAL_TRANSFER))
        name = (attrs.get("name", getattr(self.instance, "name", "")) or "").strip()
        if fiscal_type == PaymentMethod.FISCAL_CASH:
            attrs["is_cash"] = True
        elif attrs.get("is_cash") is True and fiscal_type != PaymentMethod.FISCAL_CASH:
            attrs["fiscal_payment_type"] = PaymentMethod.FISCAL_CASH
        if not is_active:
            attrs["is_default"] = False
            attrs["auto_select_order_type"] = None
            is_default = False
        if is_default and not is_active:
            raise serializers.ValidationError({"is_default": "El método default debe estar activo."})
        if is_active and name:
            qs = PaymentMethod.objects.filter(name__iexact=name, is_active=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({"name": "Ya existe un método activo con este nombre."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        instance = super().create(validated_data)
        self._ensure_default_consistency(instance)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        updated = super().update(instance, validated_data)
        self._ensure_default_consistency(updated)
        return updated

    def _ensure_default_consistency(self, instance: PaymentMethod) -> None:
        if instance.is_default and instance.is_active:
            PaymentMethod.objects.exclude(pk=instance.pk).filter(is_default=True).update(is_default=False)
        PaymentMethod.objects.filter(is_active=False, is_default=True).update(is_default=False)
        if not PaymentMethod.objects.filter(is_active=True, is_default=True).exists():
            fallback = PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name").first()
            if fallback:
                PaymentMethod.objects.filter(pk=fallback.pk).update(is_default=True)


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=6)
    amount_applied = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, write_only=True)
    tip_amount = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, default=Decimal("0"))
    cash_received = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, allow_null=True)
    received_by = serializers.CharField(source="received_by.username", read_only=True)
    payment_method_code = serializers.CharField(write_only=True, required=False, allow_blank=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    card_type = serializers.CharField(required=False, allow_blank=True)
    split_part = serializers.IntegerField(required=False, allow_null=True)

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
            "amount_received",
            "change_amount",
            "tip_amount",
            "amount_applied_cents",
            "amount_received_cents",
            "change_cents",
            "tip_cents",
            "split_part",
            "card_type",
            "reference",
            "received_by",
            "created_at",
        ]
        read_only_fields = ["amount_received", "change_amount", "amount_applied_cents", "amount_received_cents", "change_cents", "tip_cents"]

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
            payment_method = resolve_payment_method(code, active_only=True)
            if not payment_method:
                raise serializers.ValidationError("Payment method not found")
            attrs["payment_method"] = payment_method

        method_value = (attrs.get("method") or "").strip().lower()
        if method_value == "card" and not attrs.get("payment_method"):
            resolved_card_method = resolve_payment_method("card", active_only=True)
            if resolved_card_method:
                attrs["payment_method"] = resolved_card_method

        payment_method = attrs.get("payment_method")
        if payment_method:
            fiscal_type = getattr(payment_method, "fiscal_payment_type", "")
            if fiscal_type == PaymentMethod.FISCAL_CASH:
                attrs["method"] = "cash"
            elif fiscal_type == PaymentMethod.FISCAL_CARD:
                attrs["method"] = "card"
            elif fiscal_type == PaymentMethod.FISCAL_TRANSFER:
                attrs["method"] = "transfer"
            elif not attrs.get("method"):
                attrs["method"] = "transfer"
            if fiscal_type == PaymentMethod.FISCAL_CARD and not attrs.get("card_type"):
                attrs["card_type"] = "credit"

        payment_method = attrs.get("payment_method")
        method_value = (attrs.get("method") or "").strip().lower()
        if method_value == "card":
            attrs["card_type"] = "credit"
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


class InternalPaymentMethodChangeSerializer(serializers.Serializer):
    payment_method_code = serializers.CharField(required=False, allow_blank=True)
    payment_method_id = serializers.IntegerField(required=False)
    method_id = serializers.IntegerField(required=False)
    code = serializers.CharField(required=False, allow_blank=True)
    payment_method = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    label = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=240)

    def validate(self, attrs):
        valid_methods = list(PaymentMethod.objects.filter(is_active=True).order_by("sort_order", "name"))
        valid_methods_payload = [{"id": item.id, "code": item.code, "name": item.name} for item in valid_methods]
        self.context["valid_methods"] = valid_methods_payload

        requested_code = (
            attrs.get("payment_method_code")
            or attrs.get("code")
            or attrs.get("payment_method")
            or ""
        )
        requested_name = attrs.get("name") or attrs.get("label") or ""
        requested_id = attrs.get("payment_method_id") or attrs.get("method_id")
        self.context["requested_payment_method_code"] = requested_code
        self.context["requested_payment_method_id"] = requested_id

        method: PaymentMethod | None = None
        if requested_id is not None:
            method = PaymentMethod.objects.filter(id=requested_id, is_active=True).first()

        normalized_code = normalize_payment_method_code(str(requested_code or ""))
        if method is None and normalized_code:
            method = resolve_payment_method(normalized_code, active_only=True)

        if method is None and requested_name:
            normalized_name = normalize_payment_method_code(str(requested_name or ""))
            for candidate in valid_methods:
                if normalize_payment_method_code(candidate.name) == normalized_name:
                    method = candidate
                    break

        if method is None:
            raise serializers.ValidationError(
                {
                    "payment_method_code": ["Método de pago no válido o inactivo."],
                    "valid_methods": valid_methods_payload,
                }
            )

        attrs["payment_method_code"] = normalize_payment_method_code(method.code)
        self.context["new_method"] = method
        return attrs
