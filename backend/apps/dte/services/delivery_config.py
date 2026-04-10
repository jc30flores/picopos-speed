from __future__ import annotations

import os
from dataclasses import dataclass

from django.conf import settings


INTERNAL_BILLING_EMAIL = "facturasPDG23@gmail.com"


def _read_setting(*names: str) -> str:
    for name in names:
        value = getattr(settings, name, None)
        if value is not None and str(value).strip():
            return str(value).strip()
        env_value = os.environ.get(name)
        if env_value is not None and str(env_value).strip():
            return str(env_value).strip()
    return ""


@dataclass(frozen=True)
class DeliveryConfig:
    email_base_url: str
    email_endpoint: str
    email_api_key: str
    whatsapp_base_url: str
    whatsapp_endpoint: str
    whatsapp_api_key: str
    whatsapp_default_phone: str
    whatsapp_company_name: str

    @property
    def email_url(self) -> str:
        base = self.email_base_url.rstrip("/")
        endpoint = (self.email_endpoint or "/send").strip()
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{base}{endpoint}" if base else ""

    @property
    def whatsapp_url(self) -> str:
        base = self.whatsapp_base_url.rstrip("/")
        endpoint = (self.whatsapp_endpoint or "/send").strip()
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{base}{endpoint}" if base else ""


def resolve_delivery_config() -> DeliveryConfig:
    return DeliveryConfig(
        email_base_url=_read_setting("DELIVER_EMAIL_API_BASE_URL", "EMAIL_API_BASE_URL"),
        email_endpoint=_read_setting("DELIVER_EMAIL_API_ENDPOINT", "EMAIL_API_ENDPOINT") or "/send",
        email_api_key=_read_setting("DELIVER_EMAIL_API_KEY", "EMAIL_API_KEY"),
        whatsapp_base_url=_read_setting("WHATSAPP_DTE_API_BASE", "WHATSAPP_API_BASE"),
        whatsapp_endpoint=_read_setting("WHATSAPP_DTE_API_ENDPOINT", "WHATSAPP_API_ENDPOINT") or "/send",
        whatsapp_api_key=_read_setting("WHATSAPP_DTE_API_KEY", "WHATSAPP_API_KEY"),
        whatsapp_default_phone=_read_setting("WHATSAPP_DEFAULT_TO_PHONE"),
        whatsapp_company_name=_read_setting("WHATSAPP_EMPRESA_NOMBRE", "WHATSAPP_COMPANY_NAME"),
    )
