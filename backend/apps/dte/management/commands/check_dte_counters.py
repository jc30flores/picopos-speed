from django.core.management.base import BaseCommand
from django.db import connection

from apps.dte.models import DTEControlCounter


class Command(BaseCommand):
    help = "Verifica existencia/estructura de dte_control_counter y lista correlativos actuales."

    def handle(self, *args, **options):
        table_name = DTEControlCounter._meta.db_table
        with connection.cursor() as cursor:
            tables = connection.introspection.table_names(cursor)
            constraints = connection.introspection.get_constraints(cursor, table_name) if table_name in tables else {}

        exists = table_name in tables
        self.stdout.write(f"table={table_name} exists={exists}")
        if not exists:
            return

        unique_sets = {
            tuple(sorted(info.get("columns") or []))
            for info in constraints.values()
            if info.get("unique")
        }
        required_columns = tuple(sorted(["branch_id", "dte_type", "year", "establishment_code", "pos_code", "ambiente"]))
        self.stdout.write(
            f"unique_constraint_present={required_columns in unique_sets} expected={required_columns}"
        )

        counters = DTEControlCounter.objects.select_related("branch").order_by("branch__name", "year", "dte_type", "establishment_code", "pos_code")
        if not counters.exists():
            self.stdout.write("No counters found.")
            return

        for counter in counters:
            series = f"{counter.establishment_code}{counter.pos_code}"
            self.stdout.write(
                f"branch={counter.branch_id}:{counter.branch.name} year={counter.year} type={counter.dte_type} series={series} ambiente={counter.ambiente} last_number={counter.last_number}"
            )
