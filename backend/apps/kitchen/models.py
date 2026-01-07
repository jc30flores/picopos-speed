from django.db import models
from apps.orders.models import Order
from apps.core.models import ServiceType


class KitchenOrderView(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("delivered", "Delivered"),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="kitchen_view")
    service_type = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="kitchen_orders")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    prep_time_minutes = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"Kitchen view for {self.order_id}"
