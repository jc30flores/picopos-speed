from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class InventoryItem(models.Model):
    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=80, blank=True, default="")
    unit = models.CharField(max_length=24, default="unidad")
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    min_stock = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
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


class InventoryMovement(models.Model):
    TYPE_INITIAL_STOCK = "initial_stock"
    TYPE_STOCK_ADD = "stock_add"
    TYPE_STOCK_ADJUST = "stock_adjustment"
    TYPE_SALE_DEDUCTION = "sale_deduction"
    TYPE_REVERSAL = "reversal"
    TYPE_CHOICES = [
        (TYPE_INITIAL_STOCK, "Stock inicial"),
        (TYPE_STOCK_ADD, "Entrada"),
        (TYPE_STOCK_ADJUST, "Ajuste"),
        (TYPE_SALE_DEDUCTION, "Descuento por venta"),
        (TYPE_REVERSAL, "Reversión"),
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


class InventorySaleApplication(models.Model):
    order = models.OneToOneField("orders.Order", on_delete=models.CASCADE, related_name="inventory_application")
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-applied_at"]
