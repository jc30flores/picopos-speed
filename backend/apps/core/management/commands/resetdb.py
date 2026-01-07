import subprocess
from django.conf import settings
from django.core.management import BaseCommand, call_command, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Drop and recreate the database, then run migrations and initdb."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirm database reset")

    def handle(self, *args, **options):
        if not options.get("yes"):
            raise CommandError("This will DROP the database. Pass --yes to continue.")

        default_db = settings.DATABASES["default"]
        db_name = default_db.get("NAME")
        db_user = default_db.get("USER")
        if not db_name:
            raise CommandError("Database NAME is not configured")

        self.stdout.write(self.style.WARNING(f"Resetting database '{db_name}'..."))
        self._close_connections()
        self._drop_database(db_name, db_user)
        self._create_database(db_name, db_user)

        call_command("migrate")
        call_command("initdb")

        self.stdout.write(self.style.SUCCESS("Database reset complete."))

    def _close_connections(self):
        for conn in connections.all():
            conn.close()

    def _drop_database(self, db_name: str, db_user: str | None):
        drop_cmd = ["dropdb", "--if-exists", db_name]
        if db_user:
            drop_cmd.extend(["-U", db_user])
        result = subprocess.run(drop_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise CommandError(f"dropdb failed: {result.stderr.strip()}")

    def _create_database(self, db_name: str, db_user: str | None):
        create_cmd = ["createdb", db_name]
        if db_user:
            create_cmd.extend(["-O", db_user])
        result = subprocess.run(create_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise CommandError(f"createdb failed: {result.stderr.strip()}")
