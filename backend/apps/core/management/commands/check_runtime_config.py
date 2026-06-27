import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

SECRET_NAMES = {"DJANGO_SECRET_KEY", "DB_PASSWORD", "DTE_API_TOKEN"}

class Command(BaseCommand):
    help = "Valida la configuración runtime sin modificar estado."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true")
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        strict = options["strict"] or getattr(settings, "DJANGO_CONFIG_MODE", "legacy") == "strict"
        checks = []
        def add(name, ok=True, level="OK", message=""):
            checks.append({"name": name, "level": level if ok else "ERROR", "ok": bool(ok), "message": message if not ok or level == "WARNING" else ""})
        required = ["DJANGO_CONFIG_MODE", "DJANGO_SECRET_KEY", "DJANGO_DEBUG", "ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "TIME_ZONE", "MEDIA_ROOT", "STATIC_ROOT"]
        add("DJANGO_CONFIG_MODE", getattr(settings, "DJANGO_CONFIG_MODE", "legacy") in {"legacy", "strict"})
        add("DJANGO_DEBUG", isinstance(settings.DEBUG, bool))
        for name in ["ALLOWED_HOSTS", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"]:
            add(name, bool(getattr(settings, name, [])), message="lista vacía")
        db = settings.DATABASES["default"]
        mapping = {"DB_HOST":"HOST", "DB_PORT":"PORT", "DB_NAME":"NAME", "DB_USER":"USER", "DB_PASSWORD":"PASSWORD"}
        for public, key in mapping.items():
            val = db.get(key)
            add(public, bool(val) if strict else True, message=f"Falta {public}" if strict and not val else "")
        add("DJANGO_SECRET_KEY", bool(settings.SECRET_KEY and (not strict or settings.SECRET_KEY != "dev-secret-key")), message="Falta DJANGO_SECRET_KEY")
        add("TIME_ZONE", bool(settings.TIME_ZONE))
        add("MEDIA_ROOT", bool(settings.MEDIA_ROOT))
        add("STATIC_ROOT", bool(settings.STATIC_ROOT))
        if getattr(settings, "DJANGO_CONFIG_MODE", "legacy") == "legacy":
            checks.append({"name":"LEGACY_FALLBACKS", "level":"WARNING", "ok": True, "message":"Se está usando fallback legacy"})
        if os.environ.get("DTE_ENABLED", "").lower() in {"1","true","yes","on"}:
            add("DTE_BASE_URL", bool(getattr(settings, "DTE_BASE_URL", "")))
            add("DTE_API_TOKEN", bool(getattr(settings, "DTE_API_TOKEN", "")))
        failed = [c for c in checks if not c["ok"]]
        if options["as_json"]:
            self.stdout.write(json.dumps({"ok": not failed, "strict": strict, "checks": checks}, ensure_ascii=False))
        else:
            for c in checks:
                msg = f" {c['message']}" if c.get("message") else ""
                self.stdout.write(f"[{c['level']}] {c['name']}{msg}")
        if failed and strict:
            raise CommandError("Configuración runtime inválida")
