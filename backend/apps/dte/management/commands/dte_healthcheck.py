from django.core.management.base import BaseCommand

from apps.dte.monitor import check_health_now


class Command(BaseCommand):
    help = "Diagnóstico de conectividad DTE"

    def handle(self, *args, **options):
        snapshot = check_health_now(force_log=True)
        preview = (snapshot.factura_body or snapshot.health_body or "").replace("\n", " ")[:180]
        self.stdout.write(
            "state={state} health_code={health_code} factura_code={factura_code} last_checked_at={last_checked_at} preview={preview}".format(
                state=snapshot.state,
                health_code=snapshot.health_status_code,
                factura_code=snapshot.factura_code,
                last_checked_at=snapshot.last_checked_at,
                preview=preview,
            )
        )
