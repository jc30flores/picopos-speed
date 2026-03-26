from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.cashier.printing import build_end_of_day_ticket, print_ticket_text


class Command(BaseCommand):
    help = "Build and print End of Day ticket for a cash session without closing it."

    def add_arguments(self, parser):
        parser.add_argument("session_id", type=int)

    def handle(self, *args, **options):
        session_id = options["session_id"]
        try:
            ticket = build_end_of_day_ticket(session_id)
        except Exception as exc:
            raise CommandError(f"Unable to build ticket for session {session_id}: {exc}") from exc

        self.stdout.write(ticket)
        printed, error = print_ticket_text(ticket)
        if printed:
            self.stdout.write(self.style.SUCCESS("End of day ticket printed successfully."))
            return

        self.stderr.write(self.style.WARNING(f"Ticket generated but print failed: {error}"))
