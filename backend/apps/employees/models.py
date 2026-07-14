from django.conf import settings
from django.db import models
from apps.core.models import Branch


class Employee(models.Model):
    ROLE_CHOICES = [
        ("cashier", "Cashier"),
        ("waiter", "Mesero"),
        ("kitchen", "Cocina"),
        ("manager", "Manager"),
        ("admin", "Admin"),
        ("kiosk", "Kiosk"),
        ("worker", "Worker"),
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
    is_deleted = models.BooleanField(default=False)
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
    clock_in = models.DateTimeField(null=True, blank=True)
    break_start = models.DateTimeField(null=True, blank=True)
    break_end = models.DateTimeField(null=True, blank=True)
    clock_out = models.DateTimeField(null=True, blank=True)
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    total_clock_ins = models.PositiveIntegerField(default=0)
    total_clock_outs = models.PositiveIntegerField(default=0)
    minutes_late = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="unique_attendance_employee_date")
        ]
        indexes = [models.Index(fields=["employee", "date"])]

    def __str__(self) -> str:
        return f"{self.employee.full_name} {self.date}"


class AttendanceCycle(models.Model):
    attendance_record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="cycles")
    sequence = models.PositiveIntegerField(default=1)
    clock_in_at = models.DateTimeField()
    break_start_at = models.DateTimeField(null=True, blank=True)
    break_end_at = models.DateTimeField(null=True, blank=True)
    clock_out_at = models.DateTimeField(null=True, blank=True)
    break_seconds_override = models.IntegerField(null=True, blank=True)
    adjusted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance_cycles_adjusted")
    adjusted_at = models.DateTimeField(null=True, blank=True)
    adjustment_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [
            models.UniqueConstraint(fields=["attendance_record", "sequence"], name="unique_attendance_cycle_sequence")
        ]
        indexes = [models.Index(fields=["attendance_record", "sequence"])]

    def __str__(self) -> str:
        return f"{self.attendance_record.employee.full_name} {self.attendance_record.date} ciclo {self.sequence}"


class AttendanceBreak(models.Model):
    cycle = models.ForeignKey(AttendanceCycle, on_delete=models.CASCADE, related_name="breaks")
    sequence = models.PositiveIntegerField(default=1)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "id"]
        constraints = [models.UniqueConstraint(fields=["cycle", "sequence"], name="unique_attendance_break_sequence")]


class AttendanceCycleAdjustment(models.Model):
    cycle = models.ForeignKey(AttendanceCycle, on_delete=models.CASCADE, related_name="adjustments")
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_adjustments")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="attendance_cycle_adjustments")
    changed_at = models.DateTimeField(auto_now_add=True)
    old_clock_in_at = models.DateTimeField(null=True, blank=True)
    new_clock_in_at = models.DateTimeField(null=True, blank=True)
    old_clock_out_at = models.DateTimeField(null=True, blank=True)
    new_clock_out_at = models.DateTimeField(null=True, blank=True)
    old_break_seconds_override = models.IntegerField(null=True, blank=True)
    new_break_seconds_override = models.IntegerField(null=True, blank=True)
    old_computed_break_seconds = models.IntegerField(default=0)
    new_break_seconds = models.IntegerField(default=0)
    reason = models.TextField(blank=True)


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
