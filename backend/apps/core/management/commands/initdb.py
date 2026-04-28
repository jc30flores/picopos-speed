from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connection
from apps.core.models import Branch, FeatureFlag, TaxConfig, ServiceType, Table


DEFAULT_BRANCHES = [
    {"name": "Sucursal Centro", "code": "CENTRO"},
    {"name": "Sucursal Norte", "code": "NORTE"},
    {"name": "Sucursal Sur", "code": "SUR"},
]

DEFAULT_SERVICE_TYPES = [
    {"key": "MESA", "label": "Mesa", "sort_order": 0},
    {"key": "PEDIDOS_YA", "label": "Pedidos Ya", "sort_order": 1},
    {"key": "PARA_LLEVAR", "label": "Para Llevar", "sort_order": 2},
    {"key": "KIOSK", "label": "Kiosk", "sort_order": 3},
]

DEFAULT_FEATURE_FLAGS = [
    {
        "key": "FF_CUSTOMERS_LOYALTY",
        "label": "Clientes y lealtad",
        "description": "Habilita el módulo de clientes, puntos y recompensas.",
    },
    {
        "key": "FF_INVENTORY",
        "label": "Inventario avanzado",
        "description": "Activa inventario, movimientos y proveedores.",
    },
    {
        "key": "FF_SHIFTS_CASH",
        "label": "Turnos y caja",
        "description": "Requiere apertura/cierre de caja y movimientos.",
    },
    {
        "key": "FF_CASH_CLOSE_ALLOW_PENDING_ORDERS",
        "label": "Cierre de caja con órdenes pendientes",
        "description": "Permite cerrar caja aunque existan órdenes pendientes.",
    },
    {
        "key": "FF_ADV_PERMISSIONS",
        "label": "Roles y permisos avanzados",
        "description": "Habilita permisos finos, PIN supervisor y auditoría avanzada.",
    },
    {
        "key": "FF_REFUNDS",
        "label": "Reembolsos y anulaciones avanzadas",
        "description": "Habilita flujos avanzados de devoluciones y reembolsos.",
    },
    {
        "key": "FF_ADV_REPORTS",
        "label": "Reportes gerenciales",
        "description": "Activa reportes avanzados y exportación.",
    },
    {
        "key": "FF_MULTI_BRANCH_ENFORCE",
        "label": "Multi-sucursal estricto",
        "description": "Forza el scoping por sucursal en todos los módulos.",
    },
    {
        "key": "FF_PUBLIC_API_WEBHOOKS",
        "label": "API pública y webhooks",
        "description": "Habilita integraciones con API externa y webhooks.",
    },
]



class Command(BaseCommand):
    help = "Initialize base data for PicoPOS. Safe to run multiple times."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Initializing database...")
        existing_tables = set(connection.introspection.table_names())
        required_tables = {
            "core_branch",
            "core_featureflag",
            "core_servicetype",
            "core_taxconfig",
            "core_table",
        }
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
            ServiceType.objects.update_or_create(
                key=service_data["key"],
                defaults={"label": service_data["label"], "sort_order": service_data.get("sort_order", 0), "is_active": True},
            )

        TaxConfig.objects.get_or_create(
            name="IVA",
            defaults={"rate": 0.13, "is_active": True},
        )

        for flag in DEFAULT_FEATURE_FLAGS:
            FeatureFlag.objects.get_or_create(
                key=flag["key"],
                defaults={
                    "label": flag["label"],
                    "description": flag["description"],
                    "is_enabled": False,
                },
            )

        self.stdout.write(self.style.SUCCESS("Initialization complete."))
