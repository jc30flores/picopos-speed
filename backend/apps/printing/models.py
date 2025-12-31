from django.conf import settings
from django.db import models
from apps.orders.models import Order


class PrintJob(models.Model):
    TYPE_CHOICES = [
        ("kitchen", "Kitchen"),
        ("customer", "Customer"),
        ("closeout", "Closeout"),
        ("refund", "Refund"),
        ("void", "Void"),
    ]
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("rendered", "Rendered"),
        ("printed", "Printed"),
        ("failed", "Failed"),
    ]

    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="print_jobs")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    content_text = models.TextField()
    content_html = models.TextField(blank=True)
    content_pdf_path = models.CharField(max_length=255, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="print_jobs",
    )
    printed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["type", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.type} #{self.id}"
