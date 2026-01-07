from django.core.management.base import BaseCommand, CommandError
from django.db import connection


REQUIRED_TABLES = {
    "menu_category",
    "menu_product",
    "menu_modifiergroup",
    "orders_order",
    "orders_orderitem",
}


class Command(BaseCommand):
    help = "Verify required tables exist in the database."

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            tables = {row[0] for row in cursor.fetchall()}

        missing = sorted(REQUIRED_TABLES - tables)
        if missing:
            for table in missing:
                self.stdout.write(self.style.ERROR(f"Missing table: {table}"))
            raise CommandError("Schema check failed. Run migrations.")

        self.stdout.write(self.style.SUCCESS("All required tables exist."))
