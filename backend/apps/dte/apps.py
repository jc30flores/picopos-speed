import logging
import os
from pathlib import Path

from django.apps import AppConfig
from django.conf import settings
from django.utils.autoreload import autoreload_started


logger = logging.getLogger("apps.dte")


def _mask_token(token: str) -> str:
    if not token:
        return "(empty)"
    if len(token) <= 10:
        return "****"
    return f"{token[:6]}...{token[-4:]}"


def _log_secrets_enabled() -> bool:
    return _env("DTE_LOG_SECRETS", "0") in {"1", "true", "True"}


def _env(name: str, default: str = "") -> str:
    return str(getattr(settings, name, os.environ.get(name, default)) or default)


class DTEConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dte"

    def ready(self):
        env_file = Path(settings.BASE_DIR) / ".env"
        env_example_file = Path(settings.BASE_DIR) / ".env.example"

        def _watch(sender, **kwargs):
            try:
                sender.watch_file(str(env_file))
                sender.watch_file(str(env_example_file))
            except Exception:
                pass

        autoreload_started.connect(_watch, dispatch_uid="dte.watch_env")

        background_mode = (getattr(settings, "DTE_BACKGROUND_MODE", "legacy") or "legacy").strip().lower()
        if background_mode in {"external", "disabled"}:
            if os.environ.get("PICO_INSTALLER_PREFLIGHT") != "1":
                logger.debug("[DTE] background startup skipped mode=%s", background_mode)
            return

        if os.environ.get("RUN_MAIN") != "true":
            return

        from apps.dte.monitor import start_monitor
        from apps.dte.outbox import start_outbox_worker

        try:
            start_monitor()
        except Exception:  # noqa: BLE001
            logger.exception("[DTE MONITOR] failed to start")
        try:
            start_outbox_worker()
        except Exception:  # noqa: BLE001
            logger.exception("[DTE OUTBOX] failed to start")
        interval = _env("DTE_MONITOR_INTERVAL_SECONDS", "10")
        logger.info(
            "[DTE] Config loaded mh_ambiente=%s auth_header=%s auth_prefix=%s health_endpoint=%s interval=%ss",
            _env("MH_AMBIENTE", _env("DTE_AMBIENTE", "01")),
            _env("DTE_API_AUTH_HEADER", "Authorization"),
            _env("DTE_API_AUTH_PREFIX", "Bearer"),
            _env("DTE_HEALTH_ENDPOINT", "/health"),
            interval,
        )
