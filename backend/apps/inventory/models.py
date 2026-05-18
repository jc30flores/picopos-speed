from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class InventoryItem(models.Model):
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80, blank=True, default="")
    unit = models.CharField(max_length=24, default="unidad")
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    max_stock = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [models.Index(fields=["name"]), models.Index(fields=["sku"])]

    def __str__(self) -> str:
        return self.name


class CatalogProductInventoryLink(models.Model):
    catalog_product = models.ForeignKey("menu.Product", on_delete=models.CASCADE, related_name="inventory_links")
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="product_links")
    quantity_required = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0.001)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("catalog_product", "inventory_item"),)
        ordering = ["catalog_product_id", "inventory_item_id"]


class CategoryInventoryLink(models.Model):
    category = models.ForeignKey("menu.Category", on_delete=models.CASCADE, related_name="inventory_links")
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="category_links")
    quantity_required = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(0.001)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("category", "inventory_item"),)
        ordering = ["category_id", "inventory_item_id"]


class ProductInventoryOverride(models.Model):
    product = models.ForeignKey("menu.Product", on_delete=models.CASCADE, related_name="inventory_overrides")
    category_link = models.ForeignKey(CategoryInventoryLink, on_delete=models.CASCADE, related_name="product_overrides")
    quantity_required = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    is_disabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("product", "category_link"),)
        ordering = ["product_id", "category_link_id"]


class InventoryMovement(models.Model):
    TYPE_INITIAL_STOCK = "initial_stock"
    TYPE_STOCK_ADD = "stock_add"
    TYPE_STOCK_ADJUST = "stock_adjustment"
    TYPE_SALE_DEDUCTION = "sale_deduction"
    TYPE_REVERSAL = "reversal"
    TYPE_INVENTORY_ENTRY = "inventory_entry"
    TYPE_INVENTORY_LOSS = "inventory_loss"
    TYPE_INVENTORY_DAMAGED = "inventory_damaged"
    TYPE_INVENTORY_CORRECTION = "inventory_correction"
    TYPE_INVENTORY_COUNT_ADJUSTMENT = "inventory_count_adjustment"
    TYPE_CHOICES = [
        (TYPE_INITIAL_STOCK, "Stock inicial"),
        (TYPE_STOCK_ADD, "Entrada"),
        (TYPE_STOCK_ADJUST, "Ajuste"),
        (TYPE_SALE_DEDUCTION, "Descuento por venta"),
        (TYPE_REVERSAL, "Reversión"),
        (TYPE_INVENTORY_ENTRY, "Entrada de producto"),
        (TYPE_INVENTORY_LOSS, "Pérdida"),
        (TYPE_INVENTORY_DAMAGED, "Producto dañado"),
        (TYPE_INVENTORY_CORRECTION, "Corrección de stock"),
        (TYPE_INVENTORY_COUNT_ADJUSTMENT, "Ajuste por conteo"),
    ]

    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    quantity_change = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    reference_type = models.CharField(max_length=32, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    reason = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["movement_type", "created_at"]),
            models.Index(fields=["reference_type", "reference_id"]),
            models.Index(fields=["inventory_item", "created_at"]),
        ]


class InventoryCountSession(models.Model):
    TYPE_COMPLETE = "complete"
    TYPE_MANUAL = "manual"
    TYPE_CATEGORY = "category"
    TYPE_CHOICES = [
        (TYPE_COMPLETE, "Conteo completo"),
        (TYPE_MANUAL, "Conteo manual"),
        (TYPE_CATEGORY, "Conteo por categoría"),
    ]

    STATUS_DRAFT = "draft"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_FINALIZED = "finalized"
    STATUS_APPLIED = "applied"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador"),
        (STATUS_IN_PROGRESS, "En progreso"),
        (STATUS_FINALIZED, "Finalizado"),
        (STATUS_APPLIED, "Aplicado"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    code = models.CharField(max_length=32, unique=True, blank=True, default="")
    count_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_MANUAL)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_counts_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_counts_finalized")
    finalized_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_counts_applied")
    applied_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_counts_cancelled")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True, default="")
    total_items = models.PositiveIntegerField(default=0)
    counted_items = models.PositiveIntegerField(default=0)
    total_differences = models.PositiveIntegerField(default=0)
    total_positive_differences = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_negative_differences = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["count_type", "created_at"]),
            models.Index(fields=["code"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"CI-{self.id:06d}"
            super().save(update_fields=["code"])

    def refresh_summary(self, *, save=True):
        lines = list(self.lines.all())
        self.total_items = len(lines)
        self.counted_items = sum(1 for line in lines if line.counted_stock is not None)
        diffs = [line.difference for line in lines if line.counted_stock is not None and line.difference != 0]
        self.total_differences = len(diffs)
        self.total_positive_differences = sum((diff for diff in diffs if diff > 0), start=0)
        self.total_negative_differences = sum((diff for diff in diffs if diff < 0), start=0)
        if save:
            self.save(update_fields=["total_items", "counted_items", "total_differences", "total_positive_differences", "total_negative_differences", "updated_at"])

    def __str__(self) -> str:
        return self.code or f"Conteo #{self.id}"


class InventoryCountLine(models.Model):
    session = models.ForeignKey(InventoryCountSession, on_delete=models.CASCADE, related_name="lines")
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="count_lines")
    system_stock = models.DecimalField(max_digits=12, decimal_places=3)
    counted_stock = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    difference = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    note = models.CharField(max_length=255, blank=True, default="")
    stock_before_apply = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    stock_after_apply = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    movement = models.ForeignKey(InventoryMovement, null=True, blank=True, on_delete=models.SET_NULL, related_name="count_lines")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["inventory_item__name", "id"]
        unique_together = (("session", "inventory_item"),)
        indexes = [models.Index(fields=["session", "inventory_item"])]

    def recalculate_difference(self):
        self.difference = 0 if self.counted_stock is None else self.counted_stock - self.system_stock

    def save(self, *args, **kwargs):
        self.recalculate_difference()
        super().save(*args, **kwargs)


class InventorySaleApplication(models.Model):
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="inventory_application")
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_sale_applications")
    reversed_at = models.DateTimeField(null=True, blank=True)
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_sale_reversals")
    reversal_reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-applied_at"]
