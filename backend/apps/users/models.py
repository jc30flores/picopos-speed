from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("superadmin", "Superadmin"),
        ("admin", "Admin"),
        ("manager", "Manager"),
        ("cashier", "Cashier"),
        ("kitchen", "Cocina"),
        ("kiosk", "Kiosk"),
        ("worker", "Worker"),
        ("accountant", "Contador"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    pin_hash = models.CharField(max_length=128, blank=True, default="")
    pin_failed_attempts = models.PositiveIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"

    @property
    def is_pin_locked(self) -> bool:
        return bool(self.pin_locked_until and self.pin_locked_until > timezone.now())
