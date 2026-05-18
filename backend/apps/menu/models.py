import os
import re
import uuid
from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField


def normalize_category_name(name: str | None) -> str:
    return (name or "").strip().upper()


def normalize_modifier_label(name: str | None) -> str:
    collapsed = re.sub(r"\s+", " ", (name or "").strip())
    return collapsed.upper()


def product_image_upload_to(instance: "Product", filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower().lstrip(".")
    category_name = normalize_category_name(
        instance.category.name if instance.category_id else "SIN_CATEGORIA"
    )
    safe_category = re.sub(r"[^A-Z0-9_-]+", "_", category_name) or "SIN_CATEGORIA"
    filename = f"{uuid.uuid4().hex}.{extension or 'jpg'}"
    return f"{safe_category}/{filename}"


class Category(models.Model):
    INVENTORY_STOCK_POLICY_INHERIT = "inherit"
    INVENTORY_STOCK_POLICY_ALLOW = "allow"
    INVENTORY_STOCK_POLICY_WARN = "warn"
    INVENTORY_STOCK_POLICY_BLOCK = "block"
    INVENTORY_STOCK_POLICY_CHOICES = [
        (INVENTORY_STOCK_POLICY_INHERIT, "Heredar configuración global"),
        (INVENTORY_STOCK_POLICY_ALLOW, "Permitir venta aunque no haya stock"),
        (INVENTORY_STOCK_POLICY_WARN, "Advertir antes de vender"),
        (INVENTORY_STOCK_POLICY_BLOCK, "Bloquear venta si no hay stock"),
    ]

    name = models.CharField(max_length=120, unique=True)
    image = models.FileField(upload_to="categories/", blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0, db_index=True)
    inventory_stock_policy = models.CharField(max_length=16, choices=INVENTORY_STOCK_POLICY_CHOICES, default=INVENTORY_STOCK_POLICY_INHERIT)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if self.name:
            self.name = normalize_category_name(self.name)
        if self.image and getattr(self.image, "url", None):
            self.image_path = self.image.url
        elif not self.image:
            self.image_path = None
        super().save(*args, **kwargs)


class ModifierGroup(models.Model):
    name = models.CharField(max_length=120)
    image = models.CharField(max_length=255, blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    required = models.BooleanField(default=False)
    min_selection = models.PositiveIntegerField(default=0)
    max_selection = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(max_selection__gte=models.F("min_selection")),
                name="modifier_group_max_gte_min",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if self.name:
            self.name = normalize_modifier_label(self.name)
        super().save(*args, **kwargs)


class Modifier(models.Model):
    group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, related_name="modifiers")
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    image = models.CharField(max_length=255, blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["sort_order", "name"]
        unique_together = ("group", "name")

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if self.name:
            self.name = normalize_modifier_label(self.name)
        super().save(*args, **kwargs)


class ProductModifierGroup(models.Model):
    product = models.ForeignKey("Product", on_delete=models.CASCADE)
    modifier_group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, db_column="modifiergroup_id")
    show_in_pos = models.BooleanField(default=False)

    class Meta:
        db_table = "menu_product_modifier_groups"
        unique_together = (("product", "modifier_group"),)


class Product(models.Model):
    INVENTORY_STOCK_POLICY_INHERIT = "inherit"
    INVENTORY_STOCK_POLICY_ALLOW = "allow"
    INVENTORY_STOCK_POLICY_WARN = "warn"
    INVENTORY_STOCK_POLICY_BLOCK = "block"
    INVENTORY_STOCK_POLICY_CHOICES = [
        (INVENTORY_STOCK_POLICY_INHERIT, "Heredar configuración general"),
        (INVENTORY_STOCK_POLICY_ALLOW, "Permitir venta aunque no haya stock"),
        (INVENTORY_STOCK_POLICY_WARN, "Advertir antes de vender"),
        (INVENTORY_STOCK_POLICY_BLOCK, "Bloquear venta si no hay stock"),
    ]

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    sort_order = models.PositiveIntegerField(default=0, db_index=True)
    image = models.CharField(max_length=255, blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    available = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    disposable_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    disposable_apply_to = models.JSONField(default=list, blank=True)
    requires_kitchen = models.BooleanField(default=False)
    inventory_stock_policy = models.CharField(max_length=16, choices=INVENTORY_STOCK_POLICY_CHOICES, default=INVENTORY_STOCK_POLICY_INHERIT)
    modifier_groups = models.ManyToManyField(
        ModifierGroup,
        blank=True,
        related_name="products",
        through="ProductModifierGroup",
        through_fields=("product", "modifier_group"),
    )
    modifier_group_order = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["sort_order", "name", "id"]
        indexes = [models.Index(fields=["category", "available"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if self.image:
            self.image_path = f"{settings.MEDIA_URL}{self.image}"
        else:
            self.image_path = None
        super().save(*args, **kwargs)




class ProductSpecialPriceRule(models.Model):
    DISCOUNT_TYPE_FIXED_PRICE = "FIXED_PRICE"
    DISCOUNT_TYPE_PERCENT_OFF = "PERCENT_OFF"
    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_TYPE_FIXED_PRICE, "Fixed price"),
        (DISCOUNT_TYPE_PERCENT_OFF, "Percent off"),
    ]

    product = models.ForeignKey("Product", on_delete=models.CASCADE, related_name="special_price_rules")
    name = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, db_index=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    fixed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    percent_off = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    days_of_week = models.JSONField(default=list, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    applies_to_all_order_types = models.BooleanField(default=True)
    order_types = models.ManyToManyField("core.ServiceType", blank=True, related_name="product_special_price_rules")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "id"]
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["priority"]),
        ]

    def __str__(self) -> str:
        return self.name or f"Regla {self.id}"


class Discount(models.Model):
    TYPE_CHOICES = [
        ("percent", "Percent"),
        ("fixed", "Fixed"),
        ("bxgy", "Buy X Get Y"),
    ]
    APPLIES_CHOICES = [
        ("order", "Order"),
        ("products", "Products"),
        ("categories", "Categories"),
    ]

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    value = models.DecimalField(max_digits=6, decimal_places=2)
    applies_to = models.CharField(max_length=20, choices=APPLIES_CHOICES)
    is_active = models.BooleanField(default=True)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    auto_apply = models.BooleanField(default=False)
    service_types = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    days_of_week = ArrayField(models.IntegerField(), default=list, blank=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    priority = models.IntegerField(default=100)
    stackable = models.BooleanField(default=False)
    bxgy_config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "type"]),
        ]

    def __str__(self) -> str:
        return self.name


class DiscountRuleTarget(models.Model):
    discount = models.ForeignKey(Discount, on_delete=models.CASCADE, related_name="targets")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(product__isnull=False) | models.Q(category__isnull=False),
                name="discount_rule_target_product_or_category",
            )
        ]


class PriceChangeAudit(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="price_change_audits")
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    branch = models.ForeignKey("core.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="menu_price_change_audits")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="menu_price_change_audits")
    reason = models.CharField(max_length=40, default="emergency")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
