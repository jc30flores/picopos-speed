from __future__ import annotations

from decimal import Decimal

from apps.orders.models import Order


def _as_str(value: Decimal) -> str:
    return f"{value:.2f}"


def build_payload(order: Order, control_number: str, codigo_generacion: str, dte_type: str = "CF") -> dict:
    items = []
    for item in order.items.prefetch_related("applied_modifiers").all():
        items.append(
            {
                "nombre": item.product_name_snapshot,
                "codigo": item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}"),
                "cantidad": item.quantity,
                "precio_unitario": _as_str(item.price_snapshot),
                "modificadores": [
                    {"nombre": mod.modifier_name_snapshot, "precio": _as_str(mod.modifier_price_snapshot)}
                    for mod in item.applied_modifiers.all()
                ],
            }
        )

    return {
        "identificacion": {
            "tipoDte": dte_type,
            "numeroControl": control_number,
            "codigoGeneracion": codigo_generacion,
        },
        "emisor": {"sucursal": order.branch.name, "codigo": order.branch.code},
        "receptor": {"nombre": order.customer_name or "Consumidor Final", "nit": ""},
        "resumen": {"total": _as_str(order.total), "subtotal": _as_str(order.subtotal), "impuesto": _as_str(order.tax)},
        "extension": {"service_type": (order.service_type.label if order.service_type else "Sin tipo"), "channel": order.channel},
        "cuerpoDocumento": items,
        "meta": {"order_id": order.id, "order_number": order.order_number},
    }
