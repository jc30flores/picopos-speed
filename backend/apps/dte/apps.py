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

        if os.environ.get("RUN_MAIN") != "true":
            return

        from apps.dte.services.health_sentinel import start_health_sentinel

        health_url = start_health_sentinel()
        token = _env("DTE_API_TOKEN", "")
        token_display = token if _log_secrets_enabled() else _mask_token(token)
        interval = _env("DTE_HEALTH_INTERVAL_SECONDS", "5")
        config_msg = (
            "[DTE] Config loaded "
            f"MH_AMBIENTE={_env('MH_AMBIENTE', _env('DTE_AMBIENTE', '00'))} "
            f"DTE_BASE_URL={_env('DTE_BASE_URL', '')} "
            f"AUTH_HEADER={_env('DTE_API_AUTH_HEADER', 'Authorization')} "
            f"AUTH_PREFIX={_env('DTE_API_AUTH_PREFIX', 'Bearer')} "
            f"TOKEN={token_display} "
            f"HEALTH_URL={health_url} "
            f"INTERVAL={interval}s"
        )
        print(config_msg)
        logger.info(config_msg)
