from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.core.models import ServiceType


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


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
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    available = models.BooleanField(default=True)
    modifier_groups = models.ManyToManyField(ModifierGroup, blank=True, related_name="products")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["category", "available"])]

    def __str__(self) -> str:
        return self.name


class Discount(models.Model):
    TYPE_CHOICES = [
        ("percentage", "Percentage"),
        ("fixed", "Fixed"),
        ("happy-hour", "Happy Hour"),
        ("category", "Category"),
    ]
    APPLIES_CHOICES = [
        ("ticket", "Ticket"),
        ("categories", "Categories"),
        ("products", "Products"),
    ]

    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    value = models.DecimalField(max_digits=6, decimal_places=2)
    applies_to = models.CharField(max_length=20, choices=APPLIES_CHOICES)
    target_categories = models.ManyToManyField(Category, blank=True, related_name="discounts")
    target_products = models.ManyToManyField(Product, blank=True, related_name="discounts")
    days = ArrayField(models.IntegerField(), default=list)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    service_types = models.ManyToManyField(ServiceType, blank=True, related_name="discounts")
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    requires_approval = models.BooleanField(default=False)
    auto_apply = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["active", "type"]),
        ]

    def __str__(self) -> str:
        return self.name
