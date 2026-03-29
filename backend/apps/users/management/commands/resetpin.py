from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.users.pin_utils import find_active_users_matching_pin, is_valid_pin_format


class Command(BaseCommand):
    help = "Resetea el PIN (password) de un usuario. El PIN debe ser de 6 dígitos numéricos."

    def add_arguments(self, parser):
        parser.add_argument("identifier", help="Username o email del usuario")
        parser.add_argument("pin", help="Nuevo PIN de 6 dígitos")

    def handle(self, *args, **options):
        identifier = (options.get("identifier") or "").strip()
        pin = str(options.get("pin") or "").strip()

        if not is_valid_pin_format(pin):
            raise CommandError("El PIN debe tener exactamente 6 dígitos numéricos.")

        user_model = get_user_model()
        user = user_model.objects.filter(username__iexact=identifier).first()
        if user is None:
            user = user_model.objects.filter(email__iexact=identifier).first()
        if user is None:
            raise CommandError(f"No se encontró usuario con identificador '{identifier}'.")

        duplicated = find_active_users_matching_pin(pin, exclude_user_id=user.id)
        if duplicated:
            raise CommandError("PIN ya usado por otro usuario activo.")

        user.set_password(pin)
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(f"PIN actualizado para '{user.username}'."))
