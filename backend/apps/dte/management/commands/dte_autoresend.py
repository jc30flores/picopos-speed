import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dte.outbox import process_pending_dtes


class Command(BaseCommand):
    help = "Reintenta DTE pendientes"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=int(os.environ.get("DTE_AUTORETRY_BATCH_SIZE", "25")))
        parser.add_argument("--batch-size", type=int, default=int(os.environ.get("DTE_AUTORETRY_BATCH_SIZE", "25")))
        parser.add_argument("--backoff-seconds", type=int, default=int(os.environ.get("DTE_AUTORETRY_BACKOFF_SECONDS", "60")))

    def handle(self, *args, **options):
        limit = options["limit"]
        batch_size = options["batch_size"]
        backoff_seconds = options["backoff_seconds"]
        with transaction.atomic():
            count = process_pending_dtes(limit=limit, batch_size=batch_size, backoff_seconds=backoff_seconds)
        self.stdout.write(self.style.SUCCESS(f"Processed {count} pending DTE records"))
