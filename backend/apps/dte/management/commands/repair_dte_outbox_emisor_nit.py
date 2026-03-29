from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.dte.models import DTEOutbox
from apps.dte.outbox import _repair_payload_nit_if_needed
from apps.dte.services.emisor import get_emisor_nit, payload_emisor_nit


class Command(BaseCommand):
    help = "Audit or repair DTE outbox records with invalid emisor.nit payload."

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Apply automatic payload repair.")

    def handle(self, *args, **options):
        do_fix = bool(options.get("fix"))
        found = 0
        fixed = 0
        failed = 0
        rows = DTEOutbox.objects.select_related("order__branch", "dte_record").order_by("created_at")
        for row in rows.iterator():
            payload = row.payload or row.payload_json or {}
            payload_nit = payload_emisor_nit(payload)
            expected_nit = get_emisor_nit(row.order.branch if row.order_id else None)
            if payload_nit == expected_nit:
                continue
            found += 1
            self.stdout.write(
                f"id={row.id} order_id={row.order_id} payload_nit={payload_nit or '-'} expected_nit={expected_nit} created_at={timezone.localtime(row.created_at)}"
            )
            if do_fix:
                _, repaired = _repair_payload_nit_if_needed(row, payload)
                row.refresh_from_db(fields=["status"])
                if repaired:
                    fixed += 1
                elif row.status == DTEOutbox.STATUS_FAILED:
                    failed += 1
        self.stdout.write(self.style.SUCCESS(f"Inconsistent={found} fixed={fixed} failed={failed}"))
