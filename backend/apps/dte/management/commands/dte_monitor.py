import time
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.dte.config import get_dte_config_status
from apps.dte.monitor import check_health_now


class Command(BaseCommand):
    help = "Run the DTE health monitor as a dedicated process."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one check and exit.")
        parser.add_argument("--sleep-seconds", type=float, default=float(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10))
        parser.add_argument("--max-iterations", type=int, default=0, help="Stop after N cycles; 0 means forever unless --once.")
        parser.add_argument("--no-network", action="store_true", help="Do not contact DTE endpoints; useful for tests.")

    def handle(self, *args, **options):
        if not bool(getattr(settings, "DTE_MONITOR_ENABLED", True)):
            self.stdout.write("DTE monitor disabled via DTE_MONITOR_ENABLED")
            return
        iterations = 1 if options["once"] else int(options["max_iterations"] or 0)
        cycle = 0
        last_pending_log = 0.0
        while True:
            cycle += 1
            sleep_seconds = float(options["sleep_seconds"])
            config_status = get_dte_config_status()
            if options["no_network"]:
                self.stdout.write("DTE monitor no-network check skipped")
            elif not config_status.configured:
                now = time.time()
                pending_backoff = float(getattr(settings, "DTE_CONFIG_PENDING_BACKOFF_SECONDS", 60) or 60)
                cooldown = max(float(getattr(settings, "DTE_ERROR_LOG_COOLDOWN_SECONDS", 30) or 30), pending_backoff)
                if cycle == 1 or now - last_pending_log >= cooldown:
                    self.stdout.write(f"[DTE] CONFIG_PENDING reason={config_status.reason} action=not_contacting_external_api")
                    last_pending_log = now
                sleep_seconds = max(sleep_seconds, pending_backoff)
            else:
                snapshot = check_health_now(force_log=True)
                self.stdout.write(f"DTE monitor state={snapshot.state} health={snapshot.health_status_code} factura={snapshot.factura_code}")
            if options["once"] or (iterations and cycle >= iterations):
                return
            time.sleep(sleep_seconds)
