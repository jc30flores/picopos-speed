from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from apps.users.models import UserProfile
from apps.users.pin_utils import is_valid_pin_format


class Command(BaseCommand):
    help = "Create an admin user with an admin profile."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=False)
        parser.add_argument("--username", required=False)
        parser.add_argument("--password", required=False)

    def handle(self, *args, **options):
        email = options.get("email")
        username = options.get("username")
        password = options.get("password")

        if not username and email:
            username = email.split("@")[0]

        if not username:
            raise CommandError("Provide --username or --email")

        if not password:
            password = self._prompt_password()
        if not is_valid_pin_format(password):
            raise CommandError("El PIN/contraseña debe tener exactamente 6 dígitos numéricos.")

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={"email": email or ""},
        )
        if not created and not user.is_superuser:
            self.stdout.write(self.style.WARNING("User exists; updating to admin."))

        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        UserProfile.objects.update_or_create(
            user=user,
            defaults={"role": "admin", "is_active": True},
        )

        self.stdout.write(self.style.SUCCESS(f"Admin user '{user.username}' ready."))

    def _prompt_password(self) -> str:
        import getpass

        password = getpass.getpass("PIN (6 dígitos): ")
        confirm = getpass.getpass("PIN (6 dígitos, otra vez): ")
        if password != confirm:
            raise CommandError("Passwords do not match")
        if not password:
            raise CommandError("PIN cannot be empty")
        if not is_valid_pin_format(password):
            raise CommandError("El PIN debe tener exactamente 6 dígitos numéricos.")
        return password
