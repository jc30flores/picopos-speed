from django.conf import settings
from django.db import models
from django.db.models import Q


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
    tax_included = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self) -> str:
        return f"{self.name} - {self.rate}"


class ServiceType(models.Model):
    key = models.CharField(max_length=32, unique=True)
    label = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    disposables_enabled = models.BooleanField(default=False)
    color_hex = models.CharField(max_length=7, null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "label"]

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
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["key"]
        indexes = [models.Index(fields=["key"])]

    def __str__(self) -> str:
        return f"{self.key} ({'on' if self.is_enabled else 'off'})"


class SystemAppearanceSettings(models.Model):
    DEFAULT_PRIMARY = "#1F7A4D"

    primary_color = models.CharField(max_length=7, default=DEFAULT_PRIMARY)
    color_primary = models.CharField(max_length=7, default=DEFAULT_PRIMARY)
    color_primary_hover = models.CharField(max_length=7, default="#17623E")
    color_primary_soft = models.CharField(max_length=7, default="#DDF3E8")
    color_primary_border = models.CharField(max_length=7, default="#7EC8A3")
    color_primary_text = models.CharField(max_length=7, default="#0D3B26")
    color_primary_contrast = models.CharField(max_length=7, default="#FFFFFF")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appearance_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System appearance settings"
        verbose_name_plural = "System appearance settings"

    def __str__(self) -> str:
        return f"Apariencia {self.primary_color}"


class DTEGlobalSettings(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIGURED = "configured"
    STATUS_INVALID = "invalid"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_CONFIGURED, "Configurado"),
        (STATUS_INVALID, "Inválido"),
        (STATUS_DISABLED, "Desactivado"),
    ]
    AMBIENTE_TEST = "00"
    AMBIENTE_PROD = "01"
    AMBIENTE_CHOICES = [
        (AMBIENTE_TEST, "Pruebas"),
        (AMBIENTE_PROD, "Producción"),
    ]

    hacienda_enabled = models.BooleanField(default=False)
    ambiente = models.CharField(max_length=2, choices=AMBIENTE_CHOICES, default=AMBIENTE_TEST)
    base_url = models.URLField(blank=True, default="")
    api_token = models.CharField(max_length=255, blank=True, default="")
    timeout_seconds = models.PositiveIntegerField(default=15)
    retry_count = models.PositiveIntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DISABLED)
    last_connection_test_at = models.DateTimeField(null=True, blank=True)
    last_error_sanitized = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dte_global_settings_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "DTE global settings"
        verbose_name_plural = "DTE global settings"

    def __str__(self) -> str:
        return "Facturación electrónica activa" if self.hacienda_enabled else "Facturación electrónica desactivada"


class TicketSettings(models.Model):
    ticket_logo = models.FileField(upload_to="ticket_logos/", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ticket settings"
        verbose_name_plural = "Ticket settings"

    def __str__(self) -> str:
        return "Configuración de ticket"


class Customer(models.Model):
    CLIENT_TYPE_CHOICES = [("CF", "Consumidor Final"), ("CCF", "Credito Fiscal"), ("SX", "Sujeto Excluido")]

    full_name = models.CharField(max_length=160, default="")
    company_name = models.CharField(max_length=160, blank=True, default="")
    client_type = models.CharField(max_length=4, choices=CLIENT_TYPE_CHOICES, default="CF")
    dui = models.CharField(max_length=20, blank=True, default="")
    nit = models.CharField(max_length=20, blank=True, default="")
    name = models.CharField(max_length=160)
    tipo_documento = models.CharField(max_length=10, default="13")
    num_documento = models.CharField(max_length=30, default="00000000-0")
    nrc = models.CharField(max_length=30, blank=True, null=True)
    cod_actividad = models.CharField(max_length=10, blank=True, null=True)
    desc_actividad = models.CharField(max_length=200, blank=True, null=True)
    direccion_departamento = models.CharField(max_length=2, default="12")
    direccion_municipio = models.CharField(max_length=2, default="22")
    direccion_complemento = models.CharField(max_length=255, default="Direccion del cliente")
    telefono = models.CharField(max_length=20, default="00000000")
    correo = models.EmailField(blank=True, null=True)
    is_default_consumer_final = models.BooleanField(default=False)
    direccion = models.CharField(max_length=255, default="Direccion del cliente")
    department_code = models.CharField(max_length=2, default="12")
    municipality_code = models.CharField(max_length=2, default="22")
    activity_code = models.CharField(max_length=10, blank=True, default="")
    activity_description = models.CharField(max_length=200, blank=True, default="")
    is_deleted = models.BooleanField(default=False)
    is_consumer_final = models.BooleanField(default=False)
    is_iva_exempt = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_consumer_final"],
                condition=Q(is_consumer_final=True, is_deleted=False),
                name="unique_active_consumer_final_customer",
            )
        ]

    def save(self, *args, **kwargs):
        if self.full_name and not self.name:
            self.name = self.full_name
        if self.name and not self.full_name:
            self.full_name = self.name
        self.direccion_departamento = self.department_code or self.direccion_departamento
        self.direccion_municipio = self.municipality_code or self.direccion_municipio
        self.direccion_complemento = self.direccion or self.direccion_complemento
        self.cod_actividad = self.activity_code or self.cod_actividad
        self.desc_actividad = self.activity_description or self.desc_actividad
        self.telefono = self.telefono or "00000000"
        if self.client_type != "CF":
            self.is_iva_exempt = False
        super().save(*args, **kwargs)
        if self.is_default_consumer_final:
            Customer.objects.exclude(pk=self.pk).filter(is_default_consumer_final=True).update(is_default_consumer_final=False)
        if self.is_consumer_final:
            Customer.objects.exclude(pk=self.pk).filter(is_consumer_final=True, is_deleted=False).update(is_consumer_final=False)

    def __str__(self) -> str:
        return self.full_name or self.name


class GeoDepartment(models.Model):
    code = models.CharField(max_length=2, primary_key=True)
    name = models.CharField(max_length=120)

    class Meta:
        managed = False
        db_table = "geo_departments"


class GeoMunicipality(models.Model):
    id = models.IntegerField(primary_key=True, db_column="id")
    department_code = models.CharField(max_length=4, db_column="dept_code")
    municipality_code = models.CharField(max_length=4, db_column="muni_code")
    name = models.CharField(max_length=120)

    class Meta:
        managed = False
        db_table = "geo_municipalities"


class ActivityCatalog(models.Model):
    code = models.CharField(max_length=10, primary_key=True)
    description = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = "activities_catalog"
