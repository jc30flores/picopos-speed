import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.services.dte_retry import resend_record


class Command(BaseCommand):
    help = "Reintenta DTE pendientes"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=int(os.environ.get("DTE_AUTORETRY_BATCH_SIZE", "25")))

    def handle(self, *args, **options):
        limit = options["limit"]
        backoff_seconds = int(os.environ.get("DTE_AUTORETRY_BACKOFF_SECONDS", "60"))
        max_retries = int(os.environ.get("DTE_MAX_RETRIES", "5"))
        threshold = timezone.now() - timedelta(seconds=backoff_seconds)

        with transaction.atomic():
            records = (
                DTERecord.objects.select_for_update(skip_locked=True)
                .filter(status=DTERecord.STATUS_PENDING, send_attempts__lt=max_retries)
                .filter(Q(last_sent_at__isnull=True) | Q(last_sent_at__lte=threshold))
                .order_by("created_at")[:limit]
            )
            count = 0
            for record in records:
                resend_record(record)
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Processed {count} pending DTE records"))
