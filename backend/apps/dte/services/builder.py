from __future__ import annotations

from decimal import Decimal

from apps.dte.services.active_branch import get_active_branch
from apps.orders.models import Order


def _as_str(value: Decimal) -> str:
    return f"{value:.2f}"


def build_dte_payload(order: Order, numero_control: str, codigo_generacion: str, doc_type: str = "CF") -> dict:
    active_branch = get_active_branch()
    return {
        "identificacion": {
            "tipoDte": doc_type,
            "numeroControl": numero_control,
            "codigoGeneracion": codigo_generacion,
        },
        "emisor": {"sucursal": active_branch.name, "codigo": active_branch.code},
        "receptor": {"nombre": order.customer_name or "Consumidor Final", "nit": ""},
        "cuerpoDocumento": [
            {
                "nombre": item.name or "ITEM",
                "codigo": item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}"),
                "cantidad": item.quantity,
                "precioUnitario": _as_str(item.unit_price),
            }
            for item in order.items.all()
        ],
        "resumen": {
            "subtotal": _as_str(order.subtotal),
            "impuesto": _as_str(order.tax),
            "total": _as_str(order.total),
        },
        "meta": {
            "order_id": order.id,
            "order_number": order.order_number,
            "channel": order.channel,
            "service_type": (order.service_type.key if order.service_type else "SIN_TIPO"),
        },
    }
