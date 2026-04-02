from __future__ import annotations

SERVICE_TYPE_LABELS = {
    "dine_in": "DINE IN",
    "takeout": "TAKEOUT",
    "pedidos_ya": "PEDIDOS YA",
    "online": "ONLINE",
    "kiosk": "KIOSK",
}

SERVICE_TYPE_ALIASES = {
    "mesa": "dine_in",
    "dine-in": "dine_in",
    "dinein": "dine_in",
    "dine_in": "dine_in",
    "dine in": "dine_in",
    "en_local": "dine_in",
    "para_llevar": "takeout",
    "para llevar": "takeout",
    "takeout": "takeout",
    "pedidos_ya": "pedidos_ya",
    "pedidos ya": "pedidos_ya",
    "delivery": "pedidos_ya",
    "online": "online",
    "kiosk": "kiosk",
}


def normalize_service_type(value: str | None, *, default: str = "dine_in") -> str:
    normalized = str(value or "").strip().lower()
    return SERVICE_TYPE_ALIASES.get(normalized, normalized or default)
