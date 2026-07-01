import json
import os
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.dte.config import get_dte_config_status

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
        dte_background_mode = getattr(settings, "DTE_BACKGROUND_MODE", "legacy")
        add("DJANGO_CONFIG_MODE", getattr(settings, "DJANGO_CONFIG_MODE", "legacy") in {"legacy", "strict"})
        add(f"DTE_BACKGROUND_MODE={dte_background_mode}", dte_background_mode in {"legacy", "external", "disabled"})
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
        dte_config = get_dte_config_status(getattr(settings, "DTE_BASE_URL", ""), getattr(settings, "DTE_API_TOKEN", ""))
        installer_preflight = os.environ.get("PICO_INSTALLER_PREFLIGHT") == "1"
        if strict:
            if dte_config.base_url_ok:
                add("DTE_BASE_URL configurado", True)
            elif installer_preflight:
                add("DTE_BASE_URL pendiente de configuracion real", True, level="WARNING", message=dte_config.base_url_state)
            else:
                add("DTE_BASE_URL configurado", False, message=dte_config.base_url_state)
            if dte_config.token_ok:
                add("DTE_API_TOKEN configurado", True)
            elif installer_preflight:
                add("DTE_API_TOKEN pendiente de configuracion real", True, level="WARNING", message=dte_config.token_state)
            else:
                add("DTE_API_TOKEN configurado", False, message=dte_config.token_state)
            add("DTE_API_AUTH_HEADER", bool(getattr(settings, "DTE_API_AUTH_HEADER", "")))
            add("DTE_API_AUTH_PREFIX", bool(getattr(settings, "DTE_API_AUTH_PREFIX", "")))
            add("DTE_LOG_DIR", bool(getattr(settings, "DTE_LOG_DIR", "")))
            add("DTE_MONITOR_ENABLED", isinstance(getattr(settings, "DTE_MONITOR_ENABLED", True), bool))
            add("DTE_OUTBOX_WORKER_ENABLED", isinstance(getattr(settings, "DTE_OUTBOX_WORKER_ENABLED", True), bool))
            add("DTE_MAX_RETRIES", isinstance(getattr(settings, "DTE_MAX_RETRIES", 0), int))
        elif not dte_config.configured:
            add("DTE_BASE_URL pendiente de configuracion real", True, level="WARNING", message=dte_config.reason)
        if getattr(settings, "DJANGO_CONFIG_MODE", "legacy") == "legacy":
            checks.append({"name":"LEGACY_FALLBACKS", "level":"WARNING", "ok": True, "message":"Se está usando fallback legacy"})
        failed = [c for c in checks if not c["ok"]]
        if options["as_json"]:
            self.stdout.write(json.dumps({
                "ok": not failed,
                "strict": strict,
                "dte_background_mode": dte_background_mode,
                "dte_config_ready": dte_config.configured,
                "dte_config_reason": dte_config.reason,
                "checks": checks,
            }, ensure_ascii=False))
        else:
            for c in checks:
                msg = f" {c['message']}" if c.get("message") else ""
                self.stdout.write(f"[{c['level']}] {c['name']}{msg}")
        if failed and strict:
            raise CommandError("Configuración runtime inválida")
