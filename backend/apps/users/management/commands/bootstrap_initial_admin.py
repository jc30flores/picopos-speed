import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.models import UserProfile
from apps.users.pin_utils import is_valid_pin_format


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "Bootstrap the initial admin user for native installer smoke tests."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even when PICO_BOOTSTRAP_ADMIN_ENABLED is false.")

    def handle(self, *args, **options):
        enabled = _env_bool("PICO_BOOTSTRAP_ADMIN_ENABLED", default=False)
        if not enabled and not options["force"]:
            self.stdout.write("Initial admin bootstrap disabled.")
            return

        username = (os.environ.get("PICO_BOOTSTRAP_ADMIN_USERNAME") or "admin").strip()
        password = os.environ.get("PICO_BOOTSTRAP_ADMIN_PASSWORD") or ""
        if not username:
            raise CommandError("PICO_BOOTSTRAP_ADMIN_USERNAME no puede quedar vacio.")
        if not is_valid_pin_format(password):
            raise CommandError("PICO_BOOTSTRAP_ADMIN_PASSWORD debe ser un PIN de 6 digitos.")

        user_model = get_user_model()
        with transaction.atomic():
            user, created = user_model.objects.get_or_create(username=username, defaults={"email": ""})
            if created:
                user.set_password(password)
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.save()

            UserProfile.objects.update_or_create(
                user=user,
                defaults={"role": "admin", "is_active": True},
            )

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Initial admin '{username}' {action}."))
