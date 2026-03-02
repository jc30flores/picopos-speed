import uuid
from django.db import models
from django.utils import timezone

from apps.core.models import Branch
from apps.orders.models import Order


class DTERecord(models.Model):
    STATUS_PENDING = "PENDIENTE"
    STATUS_SENDING = "ENVIANDO"
    STATUS_ACCEPTED = "ACEPTADO"
    STATUS_REJECTED = "RECHAZADO"
    STATUS_INVALIDATED = "INVALIDADO"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_SENDING, "Enviando"),
        (STATUS_ACCEPTED, "Aceptado"),
        (STATUS_REJECTED, "Rechazado"),
        (STATUS_INVALIDATED, "Invalidado"),
    ]
    DTE_TYPE_CHOICES = [
        ("CF_01", "Consumidor Final (01)"),
        ("CCF_03", "Crédito Fiscal (03)"),
        ("SE_14", "Sujeto Excluido (14)"),
        ("NC_05", "Nota de Crédito (05)"),
        ("INVALIDACION", "Invalidación"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="dte_records")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="dte_records")
    dte_type = models.CharField(max_length=20, choices=DTE_TYPE_CHOICES, default="CF_01")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    ambiente = models.CharField(max_length=2, default="00")
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
    send_attempts = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=40, default="normal_send")
    error_message = models.TextField(blank=True, default="")
    error_code = models.CharField(max_length=80, blank=True, default="")
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["control_number", "dte_type"], name="dte_record_control_type_uniq"),
            models.UniqueConstraint(fields=["codigo_generacion"], condition=~models.Q(codigo_generacion=""), name="dte_record_codigo_uniq"),
            models.UniqueConstraint(fields=["hacienda_uuid"], condition=~models.Q(hacienda_uuid=""), name="dte_record_hacienda_uuid_uniq"),
        ]
        indexes = [
            models.Index(fields=["dte_type", "status"]),
            models.Index(fields=["issue_date"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["control_number"]),
            models.Index(fields=["codigo_generacion"]),
            models.Index(fields=["hacienda_uuid"]),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo_generacion:
            self.codigo_generacion = str(uuid.uuid4()).upper()
        super().save(*args, **kwargs)


class DTEControlCounter(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="dte_counters")
    ambiente = models.CharField(max_length=2, default="00")
    dte_type = models.CharField(max_length=20, default="CF_01")
    year = models.PositiveIntegerField()
    establishment_code = models.CharField(max_length=3, default="001")
    pos_code = models.CharField(max_length=3, default="001")
    last_number = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "dte_type", "year", "establishment_code", "pos_code", "ambiente"],
                name="dte_counter_context_uniq",
            )
        ]


class DTEInvalidation(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="dte_invalidations")
    dte_record = models.ForeignKey(DTERecord, on_delete=models.CASCADE, related_name="invalidations", null=True, blank=True)
    status = models.CharField(max_length=20, choices=DTERecord.STATUS_CHOICES, default=DTERecord.STATUS_PENDING)
    hacienda_state = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField()
    tipo_anulacion = models.CharField(max_length=40, default="total")
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=80, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CreditNote(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="credit_notes")
    motivo = models.TextField()
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    dte_numero_control = models.CharField(max_length=80, blank=True, default="")
    dte_codigo_generacion = models.CharField(max_length=40, blank=True, default="")
    status = models.CharField(max_length=20, choices=DTERecord.STATUS_CHOICES, default=DTERecord.STATUS_PENDING)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
