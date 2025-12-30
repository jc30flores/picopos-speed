from django.conf import settings
from django.db import models
from apps.orders.models import Order


class Payment(models.Model):
    METHOD_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("transfer", "Transfer"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reference = models.CharField(max_length=120, blank=True)
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
