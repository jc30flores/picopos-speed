from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core.models import Branch, TaxConfig, ServiceType, Table
from apps.menu.models import Category


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

DEFAULT_CATEGORIES = [
    "Tacos",
    "Burritos",
    "Bowls",
    "Quesadillas",
    "Bebidas",
    "Acompañamientos",
    "Postres",
]


class Command(BaseCommand):
    help = "Initialize base data for PicoPOS. Safe to run multiple times."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Initializing database...")

        for branch_data in DEFAULT_BRANCHES:
            branch, _ = Branch.objects.get_or_create(
                code=branch_data["code"],
                defaults={"name": branch_data["name"]},
            )
            TaxConfig.objects.get_or_create(branch=branch, defaults={"rate": 0.08})

            for table_number in range(1, 11):
                Table.objects.get_or_create(branch=branch, number=table_number)

        for service_data in DEFAULT_SERVICE_TYPES:
            ServiceType.objects.get_or_create(
                key=service_data["key"],
                defaults={"label": service_data["label"]},
            )

        for category_name in DEFAULT_CATEGORIES:
            Category.objects.get_or_create(name=category_name)

        self.stdout.write(self.style.SUCCESS("Initialization complete."))
