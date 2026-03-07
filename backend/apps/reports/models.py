from django.db import models
from apps.core.models import Branch, ServiceType
from apps.orders.models import Order


class SaleSnapshot(models.Model):
    STATUS_CHOICES = [
        ("completado", "Completado"),
        ("anulado", "Anulado"),
        ("reembolsado", "Reembolsado"),
    ]

    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_snapshots")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="sale_snapshots")
    order_number = models.CharField(max_length=40)
    service_type = models.ForeignKey(ServiceType, on_delete=models.SET_NULL, null=True, blank=True, related_name="sale_snapshots")
    channel = models.CharField(max_length=40)
    payment_method = models.CharField(max_length=40)
    items = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    cashier_name = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="completado")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at", "status"]),
            models.Index(fields=["branch", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Sale {self.order_number}"
