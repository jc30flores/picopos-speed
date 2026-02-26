from django.conf import settings
from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=20, unique=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["code"])]

    def __str__(self) -> str:
        return self.name


class TaxConfig(models.Model):
    name = models.CharField(max_length=80, default="IVA")
    rate = models.DecimalField(max_digits=5, decimal_places=4, default=0.13)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self) -> str:
        return f"{self.name} - {self.rate}"


class ServiceType(models.Model):
    key = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label


class Table(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="tables")
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("branch", "number")
        ordering = ["branch__name", "number"]
        indexes = [models.Index(fields=["branch", "number"])]

    def __str__(self) -> str:
        return self.name or f"Table {self.number}"


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=120)
    entity_type = models.CharField(max_length=120)
    entity_id = models.CharField(max_length=120)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.entity_type}:{self.entity_id})"


class FeatureFlag(models.Model):
    key = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["key"]
        indexes = [models.Index(fields=["key"])]

    def __str__(self) -> str:
        return f"{self.key} ({'on' if self.is_enabled else 'off'})"
