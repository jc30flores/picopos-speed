from django.db import models
from apps.core.models import Branch, ServiceType, Table
from apps.menu.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
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

    order_number = models.PositiveIntegerField()
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="orders")
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="orders")
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    customer_name = models.CharField(max_length=120, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="unpaid")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["service_type"]),
            models.Index(fields=["branch", "order_number"]),
        ]
        unique_together = ("branch", "order_number")

    def __str__(self) -> str:
        return f"Order {self.order_number}"


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

    class Meta:
        indexes = [models.Index(fields=["order"]) ]

    def __str__(self) -> str:
        return self.discount_name_snapshot
