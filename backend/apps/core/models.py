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
    branch = models.OneToOneField(Branch, on_delete=models.CASCADE, related_name="tax_config")
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["branch", "is_active"])]

    def __str__(self) -> str:
        return f"{self.branch.name} - {self.rate}"


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
