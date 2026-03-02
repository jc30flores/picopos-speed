import uuid
from django.db import models
from django.utils import timezone

from apps.core.models import Branch
from apps.orders.models import Order


class DTERecord(models.Model):
    STATUS_CHOICES = [
        ("enviando", "Enviando"),
        ("pendiente", "Pendiente"),
        ("aceptado", "Aceptado"),
        ("rechazado", "Rechazado"),
        ("invalidado", "Invalidado"),
    ]
    DTE_TYPE_CHOICES = [
        ("CF", "Consumidor Final"),
        ("CCF", "Crédito Fiscal"),
        ("NC", "Nota de Crédito"),
        ("INVALIDATION", "Invalidación"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="dte_records")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="dte_records")
    dte_type = models.CharField(max_length=20, choices=DTE_TYPE_CHOICES, default="CF")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendiente")
    control_number = models.CharField(max_length=80)
    codigo_generacion = models.CharField(max_length=40, default="", blank=True)
    hacienda_uuid = models.CharField(max_length=160, blank=True, default="")
    sello_recepcion = models.CharField(max_length=160, blank=True, default="")
    hacienda_state = models.CharField(max_length=80, blank=True, default="")
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    receiver_nit = models.CharField(max_length=20, blank=True, default="")
    receiver_name = models.CharField(max_length=180, blank=True, default="")
    issue_date = models.DateField(default=timezone.localdate)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    attempt_number = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=40, default="normal_send")
    error_message = models.TextField(blank=True, default="")
    error_code = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dte_type", "status"]),
            models.Index(fields=["issue_date"]),
            models.Index(fields=["order", "dte_type", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo_generacion:
            self.codigo_generacion = str(uuid.uuid4()).upper()
        super().save(*args, **kwargs)


class DTEControlCounter(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="dte_counters")
    ambiente = models.CharField(max_length=20, default="test")
    dte_type = models.CharField(max_length=20, default="CF")
    year = models.PositiveIntegerField()
    establishment_code = models.CharField(max_length=12, default="000")
    pos_code = models.CharField(max_length=12, default="000")
    last_number = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (
            "branch",
            "ambiente",
            "dte_type",
            "year",
            "establishment_code",
            "pos_code",
        )


class DTEInvalidation(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="dte_invalidations")
    status = models.CharField(max_length=20, default="pendiente")
    hacienda_state = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField()
    tipo_anulacion = models.CharField(max_length=40, default="total")
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CreditNote(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="credit_notes")
    motivo = models.TextField()
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dte_numero_control = models.CharField(max_length=80, blank=True, default="")
    dte_codigo_generacion = models.CharField(max_length=40, blank=True, default="")
    dte_status = models.CharField(max_length=20, default="pendiente")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
