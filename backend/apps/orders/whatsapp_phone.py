from __future__ import annotations

from dataclasses import dataclass

from rest_framework import serializers


SUPPORTED_COUNTRIES = {"ESA", "USA"}


@dataclass(frozen=True)
class WhatsAppClientPhone:
    country: str
    e164: str
    digits: str


def _digits_only(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def normalize_whatsapp_num_cliente(*, raw_number: str | None, raw_country: str | None) -> WhatsAppClientPhone | None:
    number = str(raw_number or "").strip()
    country = str(raw_country or "").strip().upper()
    if not number:
        if country:
            raise serializers.ValidationError({"whatsapp_num_cliente": "Ingresa el número o deja país vacío."})
        return None
    if country not in SUPPORTED_COUNTRIES:
        raise serializers.ValidationError({"whatsapp_num_cliente_country": "Selecciona país válido (ESA o USA)."})
    digits = _digits_only(number)
    if country == "ESA":
        if digits.startswith("503") and len(digits) == 11:
            subscriber = digits[3:]
        else:
            subscriber = digits
        if len(subscriber) != 8:
            raise serializers.ValidationError({"whatsapp_num_cliente": "Para ESA usa 8 dígitos (ej. 7123-4567)."})
        return WhatsAppClientPhone(country="ESA", e164=f"+503{subscriber}", digits=subscriber)
    if country == "USA":
        if digits.startswith("1") and len(digits) == 11:
            subscriber = digits[1:]
        else:
            subscriber = digits
        if len(subscriber) != 10:
            raise serializers.ValidationError({"whatsapp_num_cliente": "Para USA usa 10 dígitos."})
        return WhatsAppClientPhone(country="USA", e164=f"+1{subscriber}", digits=subscriber)
    raise serializers.ValidationError({"whatsapp_num_cliente_country": "País no soportado."})
