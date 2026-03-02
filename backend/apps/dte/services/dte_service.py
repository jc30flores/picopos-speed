from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings

from apps.dte.models import DTEBranchConfig, DTERecord


logger = logging.getLogger(__name__)


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


def _resolve_branch_config(order):
    cfg = DTEBranchConfig.objects.filter(branch=order.branch, is_active=True).first()
    if cfg:
        return {
            "nit": cfg.emisor_nit,
            "nrc": cfg.emisor_nrc,
            "nombre": cfg.emisor_nombre,
            "nombreComercial": cfg.emisor_nombre_comercial,
            "codActividad": cfg.cod_actividad,
            "descActividad": cfg.desc_actividad,
            "tipoEstablecimiento": cfg.tipo_establecimiento,
            "codEstableMH": cfg.cod_estable_mh,
            "codEstable": cfg.cod_estable,
            "codPuntoVentaMH": cfg.cod_punto_venta_mh,
            "codPuntoVenta": cfg.cod_punto_venta,
            "departamento": cfg.direccion_departamento,
            "municipio": cfg.direccion_municipio,
            "complemento": cfg.direccion_complemento,
            "telefono": cfg.telefono,
            "correo": cfg.correo,
        }
    return {
        "nit": _get_env("DTE_EMISOR_DUI"),
        "nrc": "",
        "nombre": _get_env("DTE_NOMBRE_COMERCIAL") or "Pico de Gallo",
        "nombreComercial": _get_env("DTE_NOMBRE_COMERCIAL") or "Pico de Gallo",
        "codActividad": "",
        "descActividad": "",
        "tipoEstablecimiento": "",
        "codEstableMH": "M001",
        "codEstable": "M001",
        "codPuntoVentaMH": "P001",
        "codPuntoVenta": "P001",
        "departamento": "",
        "municipio": "",
        "complemento": "",
        "telefono": _get_env("DTE_EMISOR_TELEFONO"),
        "correo": _get_env("DTE_EMISOR_CORREO"),
    }


def build_payload_cf(order, control_number: str, generation_code: str, ambiente: str) -> dict:
    emisor = _resolve_branch_config(order)
    if not emisor.get("nit"):
        raise DTEPreflightError("Falta configuración DTE del emisor: NIT/identificador")

    dte = {
        "identificacion": {
            "tipoDte": "01",
            "ambiente": ambiente,
            "codigoGeneracion": generation_code,
            "numeroControl": control_number,
        },
        "emisor": emisor,
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


def send_to_bridge(dte_type: str, payload: dict, branch_name: str = "") -> dict:
    mode = _get_env("DTE_BRIDGE_MODE", "mock").lower()
    if mode == "mock":
        logger.info("DTE SEND >>> (tipo=%s, sucursal=%s, ambiente=%s)\n%s", dte_type, branch_name, payload.get("dte", {}).get("identificacion", {}).get("ambiente"), json.dumps(payload, ensure_ascii=False, indent=2))
        mock_resp = {
            "success": True,
            "uuid": payload.get("dte", {}).get("identificacion", {}).get("codigoGeneracion", ""),
            "respuesta_hacienda": {"estado": "PROCESADO", "selloRecibido": "SELLO-MOCK"},
        }
        logger.info("DTE RESP <<<\n%s", json.dumps(mock_resp, ensure_ascii=False, indent=2))
        return mock_resp

    url = build_dte_url(dte_type)
    timeout = int(_get_env("DTE_TIMEOUT_SECONDS", "30"))
    logger.info("DTE SEND >>> (tipo=%s, sucursal=%s, ambiente=%s)\n%s", dte_type, branch_name, payload.get("dte", {}).get("identificacion", {}).get("ambiente"), json.dumps(payload, ensure_ascii=False, indent=2))
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=build_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
            logger.info("DTE RESP <<<\n%s", json.dumps(parsed, ensure_ascii=False, indent=2))
            return parsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"error": {"message": body}}
        parsed.setdefault("success", False)
        parsed.setdefault("http_status", exc.code)
        logger.error("DTE HTTP ERROR status=%s body=%s", exc.code, body)
        logger.info("DTE RESP <<<\n%s", json.dumps(parsed, ensure_ascii=False, indent=2))
        return parsed
    except Exception as exc:
        parsed = {"success": False, "error": {"message": str(exc)}, "offline": True}
        logger.exception("DTE SEND ERROR")
        logger.info("DTE RESP <<<\n%s", json.dumps(parsed, ensure_ascii=False, indent=2))
        return parsed


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
