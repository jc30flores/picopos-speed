from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.cashier.services import CashDrawerError, CashDrawerService


class Command(BaseCommand):
    help = "Send test line and open pulse to configured cash drawer."

    def handle(self, *args, **options):
        service = CashDrawerService()
        try:
            result = service.open_drawer()
        except CashDrawerError as exc:
            self.stderr.write(self.style.ERROR(f"Cash drawer test failed: {exc}"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                "Cash drawer test completed "
                f"(vendor={hex(result.vendor_id)} product={hex(result.product_id)} interface={result.interface} "
                f"out_ep={hex(result.out_endpoint)} in_ep={hex(result.in_endpoint) if result.in_endpoint is not None else 'N/A'})"
            )
        )
