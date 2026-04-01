from django.conf import settings
from django.db import models
from apps.orders.models import Order
from apps.cashier.models import CashSession


class PaymentMethod(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    is_cash = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]

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
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    card_type = models.CharField(max_length=10, blank=True, default="")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    cash_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
