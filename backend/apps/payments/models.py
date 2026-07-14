from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from apps.orders.models import Order
from apps.core.models import ServiceType
from apps.cashier.models import CashSession


class PaymentMethod(models.Model):
    FISCAL_CASH = "CASH"
    FISCAL_CARD = "CARD"
    FISCAL_TRANSFER = "TRANSFER"
    FISCAL_PAYMENT_TYPE_CHOICES = [
        (FISCAL_CASH, "Efectivo"),
        (FISCAL_CARD, "Tarjeta"),
        (FISCAL_TRANSFER, "Transferencia"),
    ]

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    is_cash = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    color_hex = models.CharField(max_length=7, blank=True, default="")
    fiscal_payment_type = models.CharField(
        max_length=12,
        choices=FISCAL_PAYMENT_TYPE_CHOICES,
        default=FISCAL_TRANSFER,
    )
    is_default = models.BooleanField(default=False)
    auto_print_ticket = models.BooleanField(default=False)
    auto_select_order_type = models.ForeignKey(
        ServiceType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auto_payment_methods",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=Q(is_default=True, is_active=True),
                name="unique_active_default_payment_method",
            ),
        ]

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.fiscal_payment_type == self.FISCAL_CASH:
            self.is_cash = True
        elif self.is_cash:
            self.fiscal_payment_type = self.FISCAL_CASH
        if not self.is_active:
            self.is_default = False
            self.auto_select_order_type = None
        if self.is_default and self.is_active:
            PaymentMethod.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Payment(models.Model):
    METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("transfer", "Transfer"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, null=True, blank=True, related_name="payments")
    reporting_payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments_reporting_override",
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    card_type = models.CharField(max_length=10, blank=True, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cash_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_applied_cents = models.IntegerField(default=0)
    amount_received_cents = models.IntegerField(default=0)
    change_cents = models.IntegerField(default=0)
    tip_cents = models.IntegerField(default=0)
    split_part = models.PositiveIntegerField(null=True, blank=True)
    reference = models.CharField(max_length=120, blank=True)
    cash_session = models.ForeignKey(
        CashSession,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
            models.Index(fields=["method"]),
        ]

    def __str__(self) -> str:
        return f"{self.order_id} {self.method} {self.amount}"


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    table_session = models.ForeignKey(
        "orders.TableSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations",
    )
    table_guest = models.ForeignKey(
        "orders.TableGuest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_allocations",
    )
    guest_number = models.PositiveIntegerField(null=True, blank=True)
    guest_label = models.CharField(max_length=64, blank=True, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_cents = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["payment", "created_at"], name="payments_pa_payment_a3c90e_idx"),
            models.Index(fields=["table_session", "guest_number"], name="payments_pa_table_s_f0c5f2_idx"),
            models.Index(fields=["table_guest"], name="payments_pa_table_g_2fb5a8_idx"),
            models.Index(fields=["order_item"], name="payments_pa_order_i_c9b65a_idx"),
        ]

    def __str__(self) -> str:
        label = self.guest_label or (f"Persona {self.guest_number}" if self.guest_number else "Cuenta")
        return f"Payment#{self.payment_id} {label} {self.amount}"


class Refund(models.Model):
    METHOD_CHOICES = Payment.METHOD_CHOICES

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="refunds")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.PROTECT, null=True, blank=True, related_name="refunds")
    original_payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds",
    )
    cash_session = models.ForeignKey(
        CashSession,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refunds",
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tip_refunded = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason = models.TextField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_refunds",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_refunds",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order", "created_at"]),
            models.Index(fields=["method"]),
        ]

    def __str__(self) -> str:
        return f"Refund {self.order_id} {self.method} {self.amount}"


class PaymentMethodChangeLog(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="method_change_logs")
    old_payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="old_payment_method_changes",
    )
    new_payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.PROTECT,
        related_name="new_payment_method_changes",
    )
    reason = models.CharField(max_length=240, blank=True, default="")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_method_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]

    def __str__(self) -> str:
        return f"Payment#{self.payment_id} {self.old_payment_method_id}->{self.new_payment_method_id}"
