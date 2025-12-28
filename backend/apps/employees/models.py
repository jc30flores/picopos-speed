from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.core.models import Branch


class Employee(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="employees")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    days_worked = models.PositiveIntegerField(default=0)
    hours_worked = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    late_arrivals = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["branch", "status"])]

    def __str__(self) -> str:
        return self.name


class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    entry_time = models.TimeField()
    exit_time = models.TimeField()
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("employee", "date")
        indexes = [models.Index(fields=["employee", "date"])]

    def __str__(self) -> str:
        return f"{self.employee.name} {self.date}"


class Schedule(models.Model):
    TYPE_CHOICES = [
        ("Fijo", "Fijo"),
        ("Turnos rotativos", "Turnos rotativos"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="schedules")
    schedule_type = models.CharField(max_length=40, choices=TYPE_CHOICES, default="Fijo")
    days = ArrayField(models.CharField(max_length=3), default=list)
    entry_time = models.TimeField()
    exit_time = models.TimeField()
    allows_overtime = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["employee", "schedule_type"])]

    def __str__(self) -> str:
        return f"{self.employee.name} - {self.schedule_type}"
