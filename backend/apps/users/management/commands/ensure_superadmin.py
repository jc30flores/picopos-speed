from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.users.models import UserProfile


DEFAULT_USERNAME = "superadmin"
DEFAULT_PIN = "102938"


class Command(BaseCommand):
    help = "Garantiza un usuario superadmin local idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=DEFAULT_USERNAME,
            defaults={"is_staff": True, "is_superuser": True, "is_active": True},
        )
        changed_fields = []
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append("is_superuser")
        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")
        if created or not user.has_usable_password():
            user.set_password(DEFAULT_PIN)
            changed_fields.append("password")
        if changed_fields:
            user.save(update_fields=list(dict.fromkeys(changed_fields)))

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={"role": "superadmin", "is_active": True},
        )
        profile_changes = []
        if profile.role != "superadmin":
            profile.role = "superadmin"
            profile_changes.append("role")
        if not profile.is_active:
            profile.is_active = True
            profile_changes.append("is_active")
        if profile_changes:
            profile.save(update_fields=profile_changes)

        self.stdout.write(self.style.SUCCESS("superadmin ensured"))
