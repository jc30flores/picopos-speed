from __future__ import annotations

from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Alias for dte_send_test (--order-id)."

    def add_arguments(self, parser):
        parser.add_argument("--order", type=int, required=True)

    def handle(self, *args, **options):
        call_command("dte_send_test", order_id=options["order"])
