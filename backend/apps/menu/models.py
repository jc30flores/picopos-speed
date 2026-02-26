import os
import re
import uuid
from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField


def normalize_category_name(name: str | None) -> str:
    return (name or "").strip().upper()


def product_image_upload_to(instance: "Product", filename: str) -> str:
    extension = os.path.splitext(filename)[1].lower().lstrip(".")
    category_name = normalize_category_name(
        instance.category.name if instance.category_id else "SIN_CATEGORIA"
    )
    safe_category = re.sub(r"[^A-Z0-9_-]+", "_", category_name) or "SIN_CATEGORIA"
    filename = f"{uuid.uuid4().hex}.{extension or 'jpg'}"
    return f"{safe_category}/{filename}"


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if self.name:
            self.name = normalize_category_name(self.name)
        super().save(*args, **kwargs)


class ModifierGroup(models.Model):
    name = models.CharField(max_length=120)
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


class Modifier(models.Model):
    group = models.ForeignKey(ModifierGroup, on_delete=models.CASCADE, related_name="modifiers")
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("group", "name")

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    image = models.CharField(max_length=255, blank=True, null=True)
    image_path = models.CharField(max_length=255, blank=True, null=True)
    available = models.BooleanField(default=True)
    requires_kitchen = models.BooleanField(default=False)
    modifier_groups = models.ManyToManyField(ModifierGroup, blank=True, related_name="products")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["category", "available"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:
        if self.image:
            self.image_path = f"{settings.MEDIA_URL}{self.image}"
        else:
            self.image_path = None
        super().save(*args, **kwargs)


class Discount(models.Model):
    TYPE_CHOICES = [
        ("percent", "Percent"),
        ("fixed", "Fixed"),
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
    auto_apply = models.BooleanField(default=True)
    service_types = ArrayField(models.CharField(max_length=32), default=list, blank=True)
    days_of_week = ArrayField(models.IntegerField(), default=list, blank=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)

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
