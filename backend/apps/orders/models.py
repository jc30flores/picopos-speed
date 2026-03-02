from django.db import models
from apps.core.models import Branch, ServiceType, Table
from apps.menu.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("waiting_payment", "Waiting Payment"),
        ("new", "New"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("delivered", "Delivered"),
        ("canceled", "Canceled"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("unpaid", "Unpaid"),
        ("partial", "Partial"),
        ("paid", "Paid"),
    ]
    CHANNEL_CHOICES = [("pos", "POS"), ("kiosk", "Kiosk"), ("online", "Online")]
    FINANCIAL_STATUS_CHOICES = [
        ("open", "Open"),
        ("paid", "Paid"),
        ("refunded_partial", "Refunded (Partial)"),
        ("refunded_full", "Refunded (Full)"),
        ("voided", "Voided"),
    ]

    order_number = models.PositiveIntegerField()
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="orders")
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting_payment")
    customer_name = models.CharField(max_length=120, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="pos")
    requires_kitchen = models.BooleanField(default=False)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    disposable_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid")
    financial_status = models.CharField(
        max_length=20,
        choices=FINANCIAL_STATUS_CHOICES,
        default="open",
    )
    refund_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["service_type"]),
            models.Index(fields=["branch", "order_number"]),
            models.Index(fields=["channel", "requires_kitchen", "status"]),
        ]
        unique_together = ("branch", "order_number")

    def __str__(self) -> str:
        return f"Order {self.order_number}"

    def recalculate_financials(self) -> None:
        from decimal import Decimal
        from django.db.models import DecimalField, ExpressionWrapper, F, Sum
        from apps.payments.models import Payment, Refund

        totals = Payment.objects.filter(order=self).aggregate(
            total_paid=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_amount"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )
        refunded = Refund.objects.filter(order=self).aggregate(
            total_refunded=Sum(
                ExpressionWrapper(
                    F("amount") + F("tip_refunded"),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            )
        )
        total_paid = totals["total_paid"] or Decimal("0")
        total_refunded = refunded["total_refunded"] or Decimal("0")
        net_paid = max(total_paid - total_refunded, Decimal("0")).quantize(Decimal("0.01"))

        if self.financial_status != "voided":
            if total_paid <= 0:
                self.payment_status = "unpaid"
                self.financial_status = "open"
            elif total_paid < self.total:
                self.payment_status = "partial"
                self.financial_status = "open"
            else:
                self.payment_status = "paid"
                if total_refunded <= 0:
                    self.financial_status = "paid"
                elif total_refunded < total_paid:
                    self.financial_status = "refunded_partial"
                else:
                    self.financial_status = "refunded_full"

        self.refund_total = total_refunded
        self.net_paid = net_paid
        self.save(
            update_fields=[
                "payment_status",
                "financial_status",
                "refund_total",
                "net_paid",
                "updated_at",
            ]
        )


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name_snapshot = models.CharField(max_length=160)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        indexes = [models.Index(fields=["order"]) ]

    def __str__(self) -> str:
        return f"{self.product_name_snapshot} x{self.quantity}"


class OrderItemModifier(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="applied_modifiers")
    modifier_name_snapshot = models.CharField(max_length=120)
    modifier_price_snapshot = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["order_item"]) ]

    def __str__(self) -> str:
        return self.modifier_name_snapshot


class AppliedDiscount(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="applied_discounts")
    discount_name_snapshot = models.CharField(max_length=160)
    discount_type_snapshot = models.CharField(max_length=20)
    discount_value_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    amount_discounted = models.DecimalField(max_digits=10, decimal_places=2)
    breakdown = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["order"]) ]

    def __str__(self) -> str:
        return self.discount_name_snapshot


class OrderFee(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="fees")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="fees", null=True, blank=True)
    fee_type = models.CharField(max_length=40, default="disposable")
    fee_name = models.CharField(max_length=120)
    unit_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        indexes = [models.Index(fields=["order", "fee_type"]) ]

    def __str__(self) -> str:
        return f"{self.fee_name} ({self.total_amount})"


class OrderInvoice(models.Model):
    HACIENDA_STATUS_CHOICES = [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="invoice")
    status = models.CharField(max_length=20, choices=HACIENDA_STATUS_CHOICES, default="pending")
    dte_number = models.CharField(max_length=80, blank=True)
    generation_code = models.CharField(max_length=120, blank=True)
    dte_status = models.CharField(max_length=20, blank=True, default="pending")
    dte_send_attempts = models.PositiveIntegerField(default=0)
    last_dte_sent_at = models.DateTimeField(null=True, blank=True)
    last_dte_error = models.TextField(blank=True)
    last_dte_error_code = models.CharField(max_length=80, blank=True)
    numero_control = models.CharField(max_length=80, blank=True)
    codigo_generacion = models.CharField(max_length=40, blank=True)
    hacienda_payload = models.JSONField(default=dict, blank=True)
    hacienda_response = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "updated_at"])]

    def __str__(self) -> str:
        return f"Invoice {self.order_id} ({self.status})"
