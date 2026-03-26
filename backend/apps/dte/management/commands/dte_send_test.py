from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.dte.services.orchestrator import transmit_sale_dte


class Command(BaseCommand):
    help = "Send DTE payload for an order id and print real response metadata."

    def add_arguments(self, parser):
        parser.add_argument("--order-id", type=int, required=True)

    def handle(self, *args, **options):
        order_id = options["order_id"]
        try:
            record = transmit_sale_dte(order_id, source="manual_test", force=True)
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f"DTE status: {record.status}"))
        self.stdout.write(f"HTTP status: {record.response_payload.get('http_status')}")
        self.stdout.write("Response body:")
        self.stdout.write(json.dumps(record.response_payload, ensure_ascii=False, indent=2))
