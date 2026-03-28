from __future__ import annotations

from decimal import Decimal

from apps.orders.models import Order


def _as_str(value: Decimal) -> str:
    return f"{value:.2f}"


def build_dte_payload(order: Order, numero_control: str, codigo_generacion: str, doc_type: str = "CF") -> dict:
    return {
        "identificacion": {
            "tipoDte": doc_type,
            "numeroControl": numero_control,
            "codigoGeneracion": codigo_generacion,
        },
        "emisor": {"sucursal": order.branch.name, "codigo": order.branch.code},
        "receptor": {"nombre": order.customer_name or "Consumidor Final", "nit": ""},
        "cuerpoDocumento": [
            {
                "nombre": item.product_name_snapshot or (item.product.name if item.product_id and item.product else "ITEM"),
                "codigo": item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}"),
                "cantidad": item.quantity,
                "precioUnitario": _as_str(item.effective_unit_price),
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
