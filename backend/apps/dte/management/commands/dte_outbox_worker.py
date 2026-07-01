import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from apps.dte.config import get_dte_config_status
from apps.dte.models import DTEOutbox
from apps.dte.outbox import process_pending_outbox

ADVISORY_LOCK_KEY = 77300101


def _try_lock() -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [ADVISORY_LOCK_KEY])
        return bool(cursor.fetchone()[0])


def _unlock() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_unlock(%s)", [ADVISORY_LOCK_KEY])


class Command(BaseCommand):
    help = "Run the DTE outbox worker as a dedicated process."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one cycle and exit.")
        parser.add_argument("--sleep-seconds", type=float, default=float(getattr(settings, "DTE_OUTBOX_INTERVAL", 2) or 2))
        parser.add_argument("--batch-size", type=int, default=int(getattr(settings, "DTE_PENDING_BATCH_SIZE", 50) or 50))
        parser.add_argument("--max-iterations", type=int, default=0, help="Stop after N cycles; 0 means forever unless --once.")
        parser.add_argument("--no-send", action="store_true", help="Dry-run queue selection only; does not transmit or mutate state.")

    def handle(self, *args, **options):
        if not bool(getattr(settings, "DTE_OUTBOX_WORKER_ENABLED", True)):
            self.stdout.write("DTE outbox worker disabled via DTE_OUTBOX_WORKER_ENABLED")
            return
        iterations = 1 if options["once"] else int(options["max_iterations"] or 0)
        cycle = 0
        last_pending_log = 0.0
        while True:
            cycle += 1
            sleep_seconds = float(options["sleep_seconds"])
            config_status = get_dte_config_status()
            if not config_status.configured:
                now = time.time()
                pending_backoff = float(getattr(settings, "DTE_CONFIG_PENDING_BACKOFF_SECONDS", 60) or 60)
                cooldown = max(float(getattr(settings, "DTE_ERROR_LOG_COOLDOWN_SECONDS", 30) or 30), pending_backoff)
                if cycle == 1 or now - last_pending_log >= cooldown:
                    self.stdout.write(f"[DTE] CONFIG_PENDING reason={config_status.reason} action=not_contacting_external_api")
                    last_pending_log = now
                processed = 0
                sleep_seconds = max(sleep_seconds, pending_backoff)
            elif not _try_lock():
                self.stdout.write("DTE outbox worker skipped: another worker holds advisory lock")
                processed = 0
            else:
                try:
                    if options["no_send"]:
                        processed = DTEOutbox.objects.filter(status=DTEOutbox.STATUS_PENDING).count()
                        self.stdout.write(f"DTE outbox dry-run pending={processed}")
                    else:
                        processed = process_pending_outbox(limit=options["batch_size"])
                        self.stdout.write(f"DTE outbox processed={processed}")
                finally:
                    _unlock()
            if options["once"] or (iterations and cycle >= iterations):
                return
            time.sleep(sleep_seconds)
