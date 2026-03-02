from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings

from apps.dte.models import DTERecord


DTE_ENDPOINT_BY_TYPE = {
    "CF_01": "/api/v1/dte/factura",
    "CCF_03": "/api/v1/dte/credito-fiscal",
    "SE_14": "/api/v1/dte/sujeto-excluido",
    "NC_05": "/api/v1/dte/nota-credito",
    "INVALIDACION": "/api/v1/dte/invalidacion",
}


class DTEPreflightError(Exception):
    pass


def _get_env(name: str, default: str = "") -> str:
    return getattr(settings, name, os.environ.get(name, default))


def build_dte_url(dte_type: str) -> str:
    base_url = (_get_env("DTE_BASE_URL") or _get_env("DTE_API_URL") or _get_env("DTE_ENDPOINT") or "").rstrip("/")
    if not base_url:
        raise DTEPreflightError("Falta configurar DTE_BASE_URL")
    endpoint = DTE_ENDPOINT_BY_TYPE.get(dte_type)
    if not endpoint:
        raise DTEPreflightError(f"Tipo DTE no soportado: {dte_type}")
    return f"{base_url}{endpoint}"


def build_headers() -> dict[str, str]:
    header = _get_env("DTE_API_AUTH_HEADER", "Authorization")
    prefix = _get_env("DTE_API_AUTH_PREFIX", "Bearer")
    token = _get_env("DTE_API_TOKEN", "")
    if not token:
        raise DTEPreflightError("Falta configurar DTE_API_TOKEN")
    return {"Content-Type": "application/json", header: f"{prefix} {token}".strip()}


def _money(v: Decimal) -> str:
    return f"{v:.2f}"


def build_payload_cf(order, control_number: str, generation_code: str, ambiente: str) -> dict:
    emisor_dui = _get_env("DTE_EMISOR_DUI")
    if not emisor_dui:
        raise DTEPreflightError("Falta configuración DTE del emisor: DTE_EMISOR_DUI")

    dte = {
        "identificacion": {
            "tipoDte": "01",
            "ambiente": ambiente,
            "codigoGeneracion": generation_code,
            "numeroControl": control_number,
        },
        "emisor": {
            "dui": emisor_dui,
            "nombreComercial": _get_env("DTE_NOMBRE_COMERCIAL"),
            "telefono": _get_env("DTE_EMISOR_TELEFONO"),
            "correo": _get_env("DTE_EMISOR_CORREO"),
        },
        "receptor": {
            "nombre": order.customer_name or "Consumidor Final",
        },
        "cuerpoDocumento": [
            {
                "descripcion": item.product_name_snapshot,
                "cantidad": item.quantity,
                "precioUnitario": _money(item.price_snapshot),
            }
            for item in order.items.all()
        ],
        "resumen": {
            "subTotal": _money(order.subtotal),
            "totalIva": _money(order.tax),
            "totalPagar": _money(order.total),
        },
        "extension": {
            "serviceType": order.service_type.key,
            "channel": order.channel,
            "orderId": order.id,
        },
    }
    return {"dte": dte}


def send_to_bridge(dte_type: str, payload: dict) -> dict:
    mode = _get_env("DTE_BRIDGE_MODE", "mock").lower()
    if mode == "mock":
        return {
            "success": True,
            "uuid": payload.get("dte", {}).get("identificacion", {}).get("codigoGeneracion", ""),
            "respuesta_hacienda": {"estado": "PROCESADO", "selloRecibido": "SELLO-MOCK"},
        }

    url = build_dte_url(dte_type)
    timeout = int(_get_env("DTE_TIMEOUT_SECONDS", "30"))
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=build_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"error": {"message": body}}
        parsed.setdefault("success", False)
        parsed.setdefault("http_status", exc.code)
        return parsed
    except Exception as exc:
        return {"success": False, "error": {"message": str(exc)}, "offline": True}


def interpret_dte_response(response: dict) -> dict:
    rh = response.get("respuesta_hacienda") or {}
    estado = str(rh.get("estado") or "").upper()

    if response.get("success") is True and estado in {"PROCESADO", "RECIBIDO"}:
        status = DTERecord.STATUS_ACCEPTED
    elif response.get("success") is False and rh:
        status = DTERecord.STATUS_REJECTED
    elif str(rh.get("status") or "").upper() == "PROCESSING":
        status = DTERecord.STATUS_PENDING
    elif response.get("offline") or int(response.get("http_status", 0) or 0) >= 500:
        status = DTERecord.STATUS_PENDING
    else:
        status = DTERecord.STATUS_PENDING

    error = response.get("error") or {}
    error_message = (
        error.get("message")
        or rh.get("descripcionMsg")
        or ""
    )

    return {
        "status": status,
        "hacienda_uuid": response.get("uuid") or rh.get("codigoGeneracion") or "",
        "sello_recepcion": rh.get("selloRecibido") or "",
        "hacienda_state": rh.get("estado") or "",
        "error_code": str(error.get("codigo_msg") or ""),
        "error_message": str(error_message),
    }
