from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.core.models import DTEGlobalSettings


DISABLED_MESSAGE = "Facturación electrónica desactivada. Las ventas se registran solo localmente."


@dataclass(frozen=True)
class DTERuntimeStatus:
    enabled: bool
    config_ready: bool
    config_status: str
    environment: str
    message: str
    base_url: str


def get_dte_runtime_status() -> DTERuntimeStatus:
    config = DTEGlobalSettings.objects.filter(pk=1).first()
    if not config or not config.hacienda_enabled:
        return DTERuntimeStatus(
            enabled=False,
            config_ready=False,
            config_status=DTEGlobalSettings.STATUS_DISABLED,
            environment="test",
            message=DISABLED_MESSAGE,
            base_url="",
        )

    base_url = (config.base_url or getattr(settings, "DTE_BASE_URL", "") or "").strip()
    token = (config.api_token or getattr(settings, "DTE_API_TOKEN", "") or "").strip()
    issuer_ready = _issuer_config_ready()
    config_ready = bool(base_url and token and issuer_ready)
    status = DTEGlobalSettings.STATUS_CONFIGURED if config_ready else DTEGlobalSettings.STATUS_PENDING
    return DTERuntimeStatus(
        enabled=True,
        config_ready=config_ready,
        config_status=status,
        environment="production" if config.ambiente == DTEGlobalSettings.AMBIENTE_PROD else "test",
        message="Facturación electrónica activa." if config_ready else "Configuración DTE pendiente. No se contactará Hacienda hasta completar API, emisor, sucursal y correlativos.",
        base_url=base_url,
    )


def is_dte_enabled() -> bool:
    return get_dte_runtime_status().enabled


def is_dte_config_ready() -> bool:
    status = get_dte_runtime_status()
    return bool(status.enabled and status.config_ready)


def _issuer_config_ready() -> bool:
    try:
        from apps.core.models import Branch
        from apps.core.models import DTEGlobalSettings
        from apps.dte.models import DTEBranchConfig, DTEControlCounter

        branch = Branch.objects.filter(is_active=True).order_by("id").first()
        cfg = DTEBranchConfig.objects.filter(branch=branch, is_active=True).first() if branch else None
        if not cfg:
            return False
        required = [
            cfg.emisor_nit,
            cfg.emisor_nrc,
            cfg.emisor_nombre,
            cfg.cod_actividad,
            cfg.desc_actividad,
            cfg.tipo_establecimiento,
            cfg.cod_estable,
            cfg.cod_punto_venta,
            cfg.direccion_departamento,
            cfg.direccion_municipio,
            cfg.direccion_complemento,
            cfg.telefono,
            cfg.correo,
        ]
        if not all(str(value or "").strip() for value in required):
            return False
        settings_row = DTEGlobalSettings.objects.filter(pk=1).first()
        ambiente = settings_row.ambiente if settings_row else DTEGlobalSettings.AMBIENTE_TEST
        return DTEControlCounter.objects.filter(branch=branch, ambiente=ambiente).exists()
    except Exception:
        return False
