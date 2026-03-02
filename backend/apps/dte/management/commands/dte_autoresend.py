from django.core.management.base import BaseCommand
from django.db import transaction

from apps.dte.models import DTERecord
from apps.dte.services.dte_retry import resend_record


class Command(BaseCommand):
    help = "Reintenta DTE pendientes"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        limit = options["limit"]
        with transaction.atomic():
            records = (
                DTERecord.objects.select_for_update(skip_locked=True)
                .filter(status="PENDIENTE")
                .order_by("created_at")[:limit]
            )
            count = 0
            for record in records:
                resend_record(record)
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Processed {count} pending DTE records"))
