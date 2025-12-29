from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from apps.core.models import Branch, TaxConfig, ServiceType, Table


DEFAULT_BRANCHES = [
    {"name": "Sucursal Centro", "code": "CENTRO"},
    {"name": "Sucursal Norte", "code": "NORTE"},
    {"name": "Sucursal Sur", "code": "SUR"},
]

DEFAULT_SERVICE_TYPES = [
    {"key": "dine-in", "label": "En local"},
    {"key": "takeout", "label": "Para llevar"},
    {"key": "delivery", "label": "Delivery"},
    {"key": "kiosk", "label": "Kiosk"},
]



class Command(BaseCommand):
    help = "Initialize base data for PicoPOS. Safe to run multiple times."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Initializing database...")
        existing_tables = set(connection.introspection.table_names())
        required_tables = {"core_branch", "core_servicetype", "core_taxconfig", "core_table"}
        missing_tables = required_tables - existing_tables
        if missing_tables:
            raise CommandError(
                f"Missing tables {sorted(missing_tables)}. Run migrations before initdb."
            )

        for branch_data in DEFAULT_BRANCHES:
            branch, _ = Branch.objects.get_or_create(
                code=branch_data["code"],
                defaults={"name": branch_data["name"]},
            )

            for table_number in range(1, 11):
                Table.objects.get_or_create(branch=branch, number=table_number)

        for service_data in DEFAULT_SERVICE_TYPES:
            ServiceType.objects.get_or_create(
                key=service_data["key"],
                defaults={"label": service_data["label"]},
            )

        TaxConfig.objects.get_or_create(
            name="IVA",
            defaults={"rate": 0.13, "is_active": True},
        )

        self.stdout.write(self.style.SUCCESS("Initialization complete."))
