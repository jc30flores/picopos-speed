import logging
import os
from pathlib import Path

from django.apps import AppConfig
from django.conf import settings
from django.utils.autoreload import autoreload_started


logger = logging.getLogger(__name__)


def _mask_token(token: str) -> str:
    if not token:
        return "(empty)"
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def _env(name: str, default: str = "") -> str:
    return str(getattr(settings, name, os.environ.get(name, default)) or default)


class DTEConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dte"

    def ready(self):
        env_file = Path(settings.BASE_DIR) / ".env"

        def _watch(sender, **kwargs):
            try:
                sender.watch_file(str(env_file))
            except Exception:
                pass

        autoreload_started.connect(_watch, dispatch_uid="dte.watch_env")

        if os.environ.get("RUN_MAIN") != "true":
            return

        logger.info("[DTE] MH_AMBIENTE=%s", _env("MH_AMBIENTE", _env("DTE_AMBIENTE", "00")))
        logger.info("[DTE] DTE_BASE_URL=%s", _env("DTE_BASE_URL", ""))
        logger.info(
            "[DTE] AUTH=%s %s token=%s",
            _env("DTE_API_AUTH_HEADER", "Authorization"),
            _env("DTE_API_AUTH_PREFIX", "Bearer"),
            _mask_token(_env("DTE_API_TOKEN", "")),
        )
        logger.info(
            "[DTE] timeout=%s retries=%s backoff=%s batch=%s",
            _env("DTE_TIMEOUT_SECONDS", "30"),
            _env("DTE_MAX_RETRIES", "5"),
            _env("DTE_AUTORETRY_BACKOFF_SECONDS", "60"),
            _env("DTE_AUTORETRY_BATCH_SIZE", "25"),
        )

        from apps.dte.services.health_sentinel import start_health_sentinel

        health_url = start_health_sentinel()
        logger.info("[DTE] sentinel enabled health_url=%s", health_url)
