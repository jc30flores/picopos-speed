from django.conf import settings
from django.db import models
from apps.core.models import Branch


class Employee(models.Model):
    ROLE_CHOICES = [
        ("cashier", "Cashier"),
        ("kitchen", "Kitchen"),
        ("manager", "Manager"),
        ("admin", "Admin"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    full_name = models.CharField(max_length=160)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee",
    )
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [models.Index(fields=["branch", "status"])]

    def __str__(self) -> str:
        return self.full_name


class AttendanceRecord(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    minutes_late = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="unique_attendance_employee_date")
        ]
        indexes = [models.Index(fields=["employee", "date"])]

    def __str__(self) -> str:
        return f"{self.employee.full_name} {self.date}"


class Schedule(models.Model):
    TYPE_CHOICES = [
        ("Fijo", "Fijo"),
        ("Turnos rotativos", "Turnos rotativos"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="schedules")
    schedule_type = models.CharField(max_length=40, choices=TYPE_CHOICES, default="Fijo")
    day_of_week = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_minutes = models.IntegerField(default=0)
    allows_overtime = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["employee", "day_of_week"])]

    def __str__(self) -> str:
        return f"{self.employee.full_name} - {self.day_of_week}"
