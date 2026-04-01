from django.conf import settings
from django.db import models
from apps.core.models import Branch


class Register(models.Model):
    name = models.CharField(max_length=120)
    station_name = models.CharField(max_length=120, blank=True, default="")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="registers")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["branch", "is_active"])]

    def __str__(self) -> str:
        return f"{self.branch.code} - {self.name}"


class CashSession(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    register = models.ForeignKey(Register, on_delete=models.PROTECT, related_name="sessions")
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="opened_cash_sessions",
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    opening_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_cash_sessions",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closing_counted_cash = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    summary_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["register"],
                condition=models.Q(closed_at__isnull=True),
                name="unique_open_session_per_register_unclosed",
            )
        ]

    def __str__(self) -> str:
        return f"{self.register.name} ({self.status})"


class CloseoutCount(models.Model):
    cash_session = models.OneToOneField(CashSession, on_delete=models.CASCADE, related_name="closeout")
    counted_cash = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    counted_card = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    counted_transfer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    counted_tips = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"Closeout {self.cash_session_id}"


class CashTransaction(models.Model):
    TYPE_CHOICES = [
        ("cash_out", "Cash Out"),
        ("cash_in", "Cash In"),
        ("expense", "Expense"),
        ("payout", "Payout"),
    ]

    session = models.ForeignKey(CashSession, on_delete=models.CASCADE, related_name="transactions")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="cash_out")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    refund = models.OneToOneField(
        "payments.Refund",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cash_transaction",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cash_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["session", "created_at"])]

    def __str__(self) -> str:
        return f"{self.type} {self.amount} ({self.session_id})"
