from django.core.management.base import BaseCommand

from apps.cashier.services.auto_close import maybe_auto_close_expired_cash_sessions


class Command(BaseCommand):
    help = "Cierra cajas vencidas por horario de atención si no hay cuentas abiertas."

    def handle(self, *args, **options):
        result = maybe_auto_close_expired_cash_sessions()
        self.stdout.write(
            self.style.SUCCESS(
                f"Autocierre terminado. Cerradas: {result['closed']}. Omitidas: {result['skipped']}."
            )
        )
