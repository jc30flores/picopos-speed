from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.cashier.models import CashSession


class Command(BaseCommand):
    help = (
        "Corrige opened_at de una sesión de caja específica dejando trazabilidad en notes. "
        "Usar cuando una sesión cerrada tenga fecha de apertura incorrecta por bug histórico."
    )

    def add_arguments(self, parser):
        parser.add_argument("--session-id", type=int, required=True)
        parser.add_argument(
            "--new-opened-at-local",
            type=str,
            required=True,
            help="Fecha/hora local El Salvador con formato YYYY-MM-DDTHH:MM:SS",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo muestra el cambio propuesto sin persistir.",
        )

    def handle(self, *args, **options):
        session_id = int(options["session_id"])
        raw_new_opened = str(options["new_opened_at_local"]).strip()
        dry_run = bool(options["dry_run"])

        session = CashSession.objects.select_related("register", "register__branch").filter(pk=session_id).first()
        if not session:
            raise CommandError(f"No existe CashSession id={session_id}")
        if session.closed_at is None:
            raise CommandError("Solo se permite corregir sesiones cerradas.")

        try:
            naive_local = datetime.fromisoformat(raw_new_opened)
        except ValueError as exc:
            raise CommandError("Formato inválido para --new-opened-at-local. Usa YYYY-MM-DDTHH:MM:SS.") from exc

        tz = timezone.get_current_timezone()
        new_opened_at = timezone.make_aware(naive_local, tz) if timezone.is_naive(naive_local) else timezone.localtime(naive_local, tz)
        if new_opened_at > session.closed_at:
            raise CommandError("new_opened_at_local no puede ser posterior a closed_at.")

        old_opened = session.opened_at
        old_local = timezone.localtime(old_opened, tz).isoformat() if old_opened else None
        new_local = timezone.localtime(new_opened_at, tz).isoformat()

        self.stdout.write(self.style.WARNING("Corrección propuesta"))
        self.stdout.write(f"  session_id: {session.id}")
        self.stdout.write(f"  branch_id: {session.register.branch_id}")
        self.stdout.write(f"  old_opened_at_db: {old_opened.isoformat() if old_opened else None}")
        self.stdout.write(f"  old_opened_at_local: {old_local}")
        self.stdout.write(f"  new_opened_at_db: {new_opened_at.isoformat()}")
        self.stdout.write(f"  new_opened_at_local: {new_local}")
        self.stdout.write(f"  closed_at_db: {session.closed_at.isoformat()}")
        self.stdout.write(f"  closed_at_local: {timezone.localtime(session.closed_at, tz).isoformat()}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: no se guardaron cambios."))
            return

        note_line = (
            f"[DATA-FIX {timezone.now().isoformat()}] opened_at corregido por comando "
            f"de {old_opened.isoformat() if old_opened else None} a {new_opened_at.isoformat()} (tz=America/El_Salvador)."
        )
        session.opened_at = new_opened_at
        session.notes = f"{session.notes}\n{note_line}" if session.notes else note_line
        session.save(update_fields=["opened_at", "notes"])
        self.stdout.write(self.style.SUCCESS("Sesión corregida y trazabilidad registrada en notes."))
