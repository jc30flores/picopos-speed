from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Check database connection details and basic query."

    def handle(self, *args, **options):
        settings = connection.settings_dict
        host = settings.get("HOST") or "localhost"
        port = settings.get("PORT") or "5432"
        name = settings.get("NAME")
        user = settings.get("USER")

        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path")
            schema = cursor.fetchone()[0]
            cursor.execute("SELECT 1")
            result = cursor.fetchone()[0]

        self.stdout.write(f"DB name: {name}")
        self.stdout.write(f"DB user: {user}")
        self.stdout.write(f"DB host: {host}")
        self.stdout.write(f"DB port: {port}")
        self.stdout.write(f"DB schema (search_path): {schema}")
        self.stdout.write(f"SELECT 1 result: {result}")
