from __future__ import annotations

import json
import logging
import os
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.conf import settings

from apps.dte.client import DTEClient
from apps.dte.models import CreditNote, DTERecord, DteInvalidationAttempt
from apps.dte.services.emisor import get_emisor_config, get_emisor_nit
from apps.dte.services.dte_parser import parse_hacienda_response
from apps.dte.services.payment_methods import get_cat017_code_and_label


logger = logging.getLogger(__name__)


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 8:
        return "****"
    return f"{token[:4]}...{token[-4:]}"


def _log_secrets_enabled() -> bool:
    return _get_env("DTE_LOG_SECRETS", "0") in {"1", "true", "True"}


def _display_token(token: str) -> str:
    return token if _log_secrets_enabled() else _mask_token(token)


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


def build_dte_url(dte_type: str) -> tuple[str, str]:
    base_url = (_get_env("DTE_BASE_URL") or _get_env("DTE_API_URL") or _get_env("DTE_ENDPOINT") or "").rstrip("/")
    endpoint = DTE_ENDPOINT_BY_TYPE.get(dte_type)
    if not endpoint:
        raise DTEPreflightError(f"Tipo DTE no soportado: {dte_type}")
    return base_url, f"{base_url}{endpoint}" if base_url else endpoint


def build_headers() -> dict[str, str]:
    header = _get_env("DTE_API_AUTH_HEADER", "Authorization")
    prefix = _get_env("DTE_API_AUTH_PREFIX", "Bearer")
    token = _get_env("DTE_API_TOKEN", "")
    if not token:
        raise DTEPreflightError("Falta configurar DTE_API_TOKEN")
    return {"Content-Type": "application/json", header: f"{prefix} {token}".strip()}


def _resolve_branch_config(order):
    return get_emisor_config(order.branch)


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def to_decimal(value: str | int | float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return Decimal(stripped)
    raise DTEPreflightError(f"Valor numérico inválido para Decimal: {type(value).__name__}")


def money(value: str | int | float | Decimal | None) -> Decimal:
    dec = to_decimal(value)
    return (dec if dec is not None else Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def json_number(value: str | int | float | Decimal | None) -> int | float:
    dec = to_decimal(value)
    if dec is None:
        return 0
    if dec == dec.to_integral_value():
        return int(dec)
    return float(dec)


_NUMERIC_KEYS = {
    "cantidad",
    "precioUni",
    "montoDescu",
    "ventaNoSuj",
    "ventaExenta",
    "ventaGravada",
    "psv",
    "noGravado",
    "ivaItem",
    "totalNoSuj",
    "totalExenta",
    "totalGravada",
    "subTotalVentas",
    "descuNoSuj",
    "descuExenta",
    "descuGravada",
    "porcentajeDescuento",
    "totalDescu",
    "subTotal",
    "ivaRete1",
    "reteRenta",
    "montoTotalOperacion",
    "totalNoGravado",
    "totalPagar",
    "totalIva",
    "saldoFavor",
    "montoPago",
}


def assert_no_string_numbers(payload: Any, path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{path}.{key}" if path else str(key)
            if key in _NUMERIC_KEYS and isinstance(value, str):
                raise DTEPreflightError(f"Campo numérico serializado como string en '{next_path}': {value!r}")
            assert_no_string_numbers(value, next_path)
        return
    if isinstance(payload, list):
        for idx, value in enumerate(payload):
            next_path = f"{path}[{idx}]"
            assert_no_string_numbers(value, next_path)


def _none_if_blank(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return value


def _has_real_dui(value: str | None) -> bool:
    if not value:
        return False
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return len(digits) == 9 and digits != "000000000"


def validate_receptor_payload(receptor: dict[str, Any]) -> None:
    tipo_documento = receptor.get("tipoDocumento")
    num_documento = receptor.get("numDocumento")
    if tipo_documento is None and num_documento is not None:
        raise DTEPreflightError("Si receptor.tipoDocumento es null, receptor.numDocumento también debe ser null")
    for key, value in receptor.items():
        if isinstance(value, str) and not value.strip():
            raise DTEPreflightError(f"receptor.{key} no puede ser string vacío")


def _number_to_words_es_usd(amount: Decimal) -> str:
    units = ["CERO", "UNO", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    teens = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    tens = ["", "", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    hundreds = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def _int_words(n: int) -> str:
        if n == 0:
            return "CERO"
        if n == 100:
            return "CIEN"
        out = []
        if n >= 100:
            out.append(hundreds[n // 100])
            n = n % 100
        if 10 <= n <= 19:
            out.append(teens[n - 10])
            n = 0
        elif n >= 20:
            t = n // 10
            u = n % 10
            if t == 2 and u > 0:
                out.append("VEINTI" + units[u].lower())
            else:
                out.append(tens[t])
                if u > 0:
                    out.append("Y")
                    out.append(units[u])
            n = 0
        if 0 < n < 10:
            out.append(units[n])
        return " ".join([x.upper() for x in out if x]).replace("VEINTIUNO", "VEINTIUNO")

    amount = _q2(amount)
    entero = int(amount)
    centavos = int((amount - Decimal(entero)) * 100)
    if entero < 1000:
        txt = _int_words(entero)
    else:
        miles = entero // 1000
        resto = entero % 1000
        miles_txt = "MIL" if miles == 1 else f"{_int_words(miles)} MIL"
        txt = f"{miles_txt} {_int_words(resto)}".strip()
    return f"{txt} DOLARES CON {centavos:02d} CENTAVOS"


def get_mh_payment_info(order) -> list[dict]:
    payments = order.payments.select_related("payment_method").order_by("id")
    if not payments.exists():
        return [{"codigo": "01", "montoPago": json_number(money(order.total)), "referencia": None, "plazo": None, "periodo": None}]
    grouped: dict[tuple[str, str | None], Decimal] = {}
    for payment in payments:
        method_code = str(payment.payment_method.code if payment.payment_method_id else payment.method or "").strip()
        reference = (payment.reference or "").strip() or None
        code, label_es = get_cat017_code_and_label(payment)
        if code == "99":
            reference = reference or label_es
            logger.warning("dte.payment_method_unknown method=%s payment_id=%s", method_code, getattr(payment, "id", None))
        key = (code, reference)
        grouped[key] = grouped.get(key, Decimal("0")) + money(payment.amount_applied if payment.amount_applied is not None else payment.amount)
    return [
        {"codigo": code, "montoPago": json_number(money(amount)), "referencia": reference, "plazo": None, "periodo": None}
        for (code, reference), amount in grouped.items()
    ]


def build_payload_cf(order, control_number: str, generation_code: str, ambiente: str) -> dict:
    from django.utils import timezone

    emisor = _resolve_branch_config(order)
    final_nit = get_emisor_nit(order.branch)
    logger.info("[DTE DEBUG] Emisor NIT final utilizado=%s branch_id=%s", final_nit, order.branch_id)
    print(f"[DTE DEBUG] Emisor NIT final utilizado={final_nit}")
    required_emisor = ["nit", "nrc", "nombre", "nombreComercial", "codActividad", "descActividad"]
    missing = [k for k in required_emisor if not emisor.get(k)]
    if missing:
        warn = f"[DTE] WARNING emisor incompleto para branch={order.branch_id}: missing={','.join(missing)}"
        print(warn)
        logger.warning(warn)

    now = timezone.localtime()
    customer = getattr(order, "customer", None)

    cuerpo = []
    num_item = 1
    total_gravada = Decimal("0.00")
    total_exenta = Decimal("0.00")
    total_iva = Decimal("0.00")
    total_descuento = Decimal("0.00")

    for item in order.items.select_related("product").prefetch_related("applied_modifiers"):
        effective_unit_price = money(item.unit_price)
        line_total = money(effective_unit_price * to_decimal(item.quantity or 0))
        line_discount = money(min(line_total, money(item.discount_amount)))
        net_line_total = _q2(line_total - line_discount)
        desc = item.name or "ITEM"
        free_mods = []
        paid_mods = []
        for mod in item.applied_modifiers.all():
            if Decimal(mod.modifier_price_snapshot or 0) > 0:
                paid_mods.append(mod)
            else:
                free_mods.append(mod.modifier_name_snapshot)
        if free_mods:
            desc = f"{desc} ({', '.join(free_mods)})"

        if order.iva_exempt:
            venta_exenta = money(net_line_total / Decimal("1.13"))
            venta_gravada = Decimal("0.00")
            iva_item = Decimal("0.00")
        else:
            venta_exenta = Decimal("0.00")
            venta_gravada = net_line_total
            base = money(net_line_total / Decimal("1.13"))
            iva_item = money(net_line_total - base)

        total_gravada += venta_gravada
        total_exenta += venta_exenta
        total_iva += iva_item
        total_descuento += line_discount

        sku = item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}")
        cuerpo.append({
            "numItem": num_item, "tipoItem": 1, "codigo": sku, "descripcion": desc,
            "cantidad": json_number(money(item.quantity)), "uniMedida": 59, "precioUni": json_number(money(effective_unit_price)),
            "montoDescu": json_number(money(line_discount)), "ventaNoSuj": json_number(Decimal("0.00")), "ventaExenta": json_number(money(venta_exenta)),
            "ventaGravada": json_number(money(venta_gravada)), "tributos": None, "psv": json_number(Decimal("0.00")), "noGravado": json_number(Decimal("0.00")),
            "ivaItem": json_number(money(iva_item)), "codTributo": None, "numeroDocumento": None,
        })
        num_item += 1

        for mod in paid_mods:
            mod_total = money(mod.modifier_price_snapshot)
            if order.iva_exempt:
                mod_exenta = money(mod_total / Decimal("1.13"))
                mod_gravada = Decimal("0.00")
                mod_iva = Decimal("0.00")
            else:
                mod_exenta = Decimal("0.00")
                mod_gravada = mod_total
                mod_iva = money(mod_total - money(mod_total / Decimal("1.13")))
            total_gravada += mod_gravada
            total_exenta += mod_exenta
            total_iva += mod_iva
            cuerpo.append({
                "numItem": num_item, "tipoItem": 1, "codigo": f"MOD-{item.id}-{num_item}", "descripcion": f"EXTRA: {mod.modifier_name_snapshot}",
                "cantidad": 1, "uniMedida": 59, "precioUni": json_number(money(mod_total)),
                "montoDescu": json_number(Decimal("0.00")), "ventaNoSuj": json_number(Decimal("0.00")), "ventaExenta": json_number(money(mod_exenta)),
                "ventaGravada": json_number(money(mod_gravada)), "tributos": None, "psv": json_number(Decimal("0.00")), "noGravado": json_number(Decimal("0.00")),
                "ivaItem": json_number(money(mod_iva)), "codTributo": None, "numeroDocumento": None,
            })
            num_item += 1

    total_pagar = _q2(total_exenta if order.iva_exempt else total_gravada)
    emisor_payload = {
        "nit": final_nit,
        "nrc": emisor.get("nrc") or "000000",
        "nombre": emisor.get("nombre") or "Pico de Gallo",
        "nombreComercial": emisor.get("nombreComercial") or "Pico de Gallo",
        "codActividad": emisor.get("codActividad") or "56101",
        "descActividad": emisor.get("descActividad") or "Restaurantes y puestos de comidas",
        "tipoEstablecimiento": emisor.get("tipoEstablecimiento") or "02",
        "codEstableMH": emisor.get("codEstableMH") or "S001",
        "codEstable": emisor.get("codEstable") or "S001",
        "codPuntoVentaMH": emisor.get("codPuntoVentaMH") or "P001",
        "codPuntoVenta": emisor.get("codPuntoVenta") or "P001",
        "telefono": emisor.get("telefono") or "00000000",
        "correo": emisor.get("correo") or "facturas@example.com",
        "direccion": {
            "departamento": emisor.get("departamento") or "12",
            "municipio": emisor.get("municipio") or "22",
            "complemento": emisor.get("complemento") or "Direccion emisor pendiente",
        },
    }

    customer_name = (getattr(customer, "full_name", "") or getattr(customer, "name", "") or "").strip().upper()
    is_consumer_final = bool(
        not customer
        or getattr(customer, "is_consumer_final", False)
        or getattr(customer, "is_default_consumer_final", False)
        or customer_name == "CONSUMIDOR FINAL"
    )
    logger.info(
        "dte.receptor.customer_snapshot customer_id=%s nombre=%s correo=%s tipo_documento=%s num_documento=%s nrc=%s cod_actividad=%s is_consumer_final=%s",
        getattr(customer, "id", None),
        (getattr(customer, "full_name", None) or getattr(customer, "name", None) or order.customer_name or "CONSUMIDOR FINAL"),
        getattr(customer, "correo", None),
        getattr(customer, "tipo_documento", None),
        getattr(customer, "num_documento", None),
        getattr(customer, "nrc", None),
        (getattr(customer, "activity_code", None) or getattr(customer, "cod_actividad", None)),
        is_consumer_final,
    )
    has_real_dui = _has_real_dui(getattr(customer, "dui", None)) or _has_real_dui(getattr(customer, "num_documento", None))
    receptor_tipo_documento = None
    receptor_num_documento = None
    if has_real_dui:
        receptor_tipo_documento = "13"
        receptor_num_documento = _none_if_blank(getattr(customer, "dui", None) or getattr(customer, "num_documento", None))
    elif not is_consumer_final:
        receptor_tipo_documento = _none_if_blank(getattr(customer, "tipo_documento", None))
        receptor_num_documento = _none_if_blank(getattr(customer, "num_documento", None))

    receptor = {
        "tipoDocumento": receptor_tipo_documento,
        "numDocumento": receptor_num_documento,
        "nombre": _none_if_blank((customer.full_name or customer.name) if customer else order.customer_name or "CONSUMIDOR FINAL"),
        "nrc": None if is_consumer_final else _none_if_blank(getattr(customer, "nrc", None)),
        "codActividad": _none_if_blank((customer.activity_code or customer.cod_actividad) if customer else None),
        "descActividad": _none_if_blank((customer.activity_description or customer.desc_actividad) if customer else None),
        "direccion": {
            "departamento": _none_if_blank((customer.department_code or customer.direccion_departamento) if customer else "12"),
            "municipio": _none_if_blank((customer.municipality_code or customer.direccion_municipio) if customer else "22"),
            "complemento": _none_if_blank((customer.direccion or customer.direccion_complemento) if customer else "Direccion del cliente"),
        },
        "telefono": _none_if_blank(customer.telefono if customer else "00000000"),
        "correo": _none_if_blank((customer.correo if customer else None)),
    }
    if receptor["correo"] is None:
        receptor["correo"] = _none_if_blank(emisor_payload.get("correo"))
    validate_receptor_payload(receptor)

    pagos = get_mh_payment_info(order)
    resumen = {
        "totalNoSuj": json_number(Decimal("0.00")), "totalExenta": json_number(money(total_exenta)), "totalGravada": json_number(money(total_gravada)),
        "subTotalVentas": json_number(money(total_pagar)), "descuNoSuj": json_number(Decimal("0.00")), "descuExenta": json_number(money(total_descuento if order.iva_exempt else Decimal("0.00"))), "descuGravada": json_number(money(total_descuento if not order.iva_exempt else Decimal("0.00"))),
        "porcentajeDescuento": json_number(Decimal("0.00")), "totalDescu": json_number(money(total_descuento)), "tributos": None, "subTotal": json_number(money(total_pagar)),
        "ivaRete1": json_number(Decimal("0.00")), "reteRenta": json_number(Decimal("0.00")), "montoTotalOperacion": json_number(money(total_pagar)), "totalNoGravado": json_number(Decimal("0.00")),
        "totalPagar": json_number(money(total_pagar)), "totalLetras": _number_to_words_es_usd(total_pagar), "totalIva": json_number(money(total_iva if not order.iva_exempt else Decimal("0.00"))),
        "saldoFavor": json_number(Decimal("0.00")), "condicionOperacion": 1,
        "pagos": pagos,
        "numPagoElectronico": None,
    }

    payload = {"dte": {
        "identificacion": {
            "version": 1, "ambiente": ambiente, "tipoDte": "01", "numeroControl": control_number, "codigoGeneracion": generation_code,
            "fecEmi": now.strftime("%Y-%m-%d"), "horEmi": now.strftime("%H:%M:%S"), "tipoOperacion": 1, "tipoModelo": 1,
            "tipoMoneda": "USD", "tipoContingencia": None, "motivoContin": None,
        },
        "emisor": emisor_payload,
        "receptor": receptor,
        "cuerpoDocumento": cuerpo,
        "resumen": resumen,
        "extension": {
            "observaciones": "Venta consumidor final - Pico de Gallo" + (" - EXENTO IVA" if order.iva_exempt else ""),
            "placaVehiculo": None, "docuRecibe": None, "nombEntrega": None, "nombRecibe": None, "docuEntrega": None,
        },
        "apendice": None, "documentoRelacionado": None, "ventaTercero": None, "otrosDocumentos": None,
    }}
    assert_no_string_numbers(payload)
    return payload


def send_to_bridge(
    dte_type: str,
    payload: dict,
    branch_name: str = "",
    *,
    order_id: int | None = None,
    payment_id: int | None = None,
    branch_id: int | None = None,
) -> dict:
    assert_no_string_numbers(payload)
    ambiente = payload.get("dte", {}).get("identificacion", {}).get("ambiente")
    payload_pretty = json.dumps(payload, ensure_ascii=False, indent=2)

    try:
        base_url, url = build_dte_url(dte_type)
    except DTEPreflightError as exc:
        base_url = (_get_env("DTE_BASE_URL") or _get_env("DTE_API_URL") or _get_env("DTE_ENDPOINT") or "").rstrip("/")
        url = f"{base_url}{DTE_ENDPOINT_BY_TYPE.get(dte_type, '')}" if base_url else DTE_ENDPOINT_BY_TYPE.get(dte_type, "")
        msg = f"[DTE] endpoint error: {exc}"
        logger.error(msg)
        print(msg)
        print(f"[DTE] MH_AMBIENTE={_get_env('MH_AMBIENTE', _get_env('DTE_AMBIENTE', '01'))} DTE_BASE_URL={base_url}")
        print(f"[DTE] DTE SEND >>> tipo={dte_type} sucursal={branch_name} ambiente={ambiente}")
        print(payload_pretty)
        return {"success": False, "error": {"message": str(exc), "type": "NETWORK_ERROR"}, "offline": True}

    print(f"[DTE] MH_AMBIENTE={_get_env('MH_AMBIENTE', _get_env('DTE_AMBIENTE', '00'))} DTE_BASE_URL={base_url}")
    print(f"[DTE] DTE ENDPOINT >>> path={DTE_ENDPOINT_BY_TYPE.get(dte_type)} url={url}")
    print(f"[DTE] DTE SEND >>> tipo={dte_type} sucursal={branch_name} ambiente={ambiente}")
    print(payload_pretty)
    logger.info("DTE ENDPOINT >>> %s", url)
    logger.info("DTE SEND >>> (tipo=%s, sucursal=%s, ambiente=%s)\n%s", dte_type, branch_name, ambiente, payload_pretty)

    if not base_url:
        msg = "[DTE] DTE_BASE_URL no configurado"
        logger.error(msg)
        print(msg)
        return {"success": False, "error": {"message": "DTE_BASE_URL no configurado", "type": "NETWORK_ERROR"}, "offline": True}

    try:
        build_headers()
    except DTEPreflightError as exc:
        msg = f"[DTE] DTE auth/header error: {exc}"
        logger.error(msg)
        print(msg)
        return {"success": False, "error": {"message": str(exc), "type": "NETWORK_ERROR"}, "offline": True}

    client = DTEClient()
    result = client.send(
        path=DTE_ENDPOINT_BY_TYPE.get(dte_type, ""),
        payload=payload,
        order_id=order_id,
        payment_id=payment_id,
        branch_id=branch_id,
    )
    body_pretty = json.dumps(result.json_body, ensure_ascii=False, indent=2)
    print(f"[DTE] DTE RESP <<< status={result.status_code} body=\n{body_pretty}")
    logger.info("DTE RESP <<< status=%s body=\n%s", result.status_code, body_pretty)
    parsed = dict(result.json_body)
    parsed.setdefault("http_status", result.status_code)
    return parsed


def interpret_dte_response(response: dict) -> dict:
    if response is None:
        response = {}
    if not isinstance(response, dict):
        response = {"raw": str(response), "http_status": 0}
    parsed_receipt = parse_hacienda_response(response or {})
    estado_top = str(response.get("estado") or "").upper()
    rh = response.get("respuesta_hacienda") or {}
    estado = str(rh.get("estado") or "").upper()
    http_status = int(response.get("http_status", 0) or 0)

    if estado_top == "ACEPTADO" or (response.get("success") is True and estado in {"PROCESADO", "RECIBIDO", "ACEPTADO"}):
        status = DTERecord.STATUS_ACCEPTED
    elif estado_top == "RECHAZADO" or (response.get("success") is False and rh):
        status = DTERecord.STATUS_REJECTED
    elif str(rh.get("status") or "").upper() == "PROCESSING":
        status = DTERecord.STATUS_PENDING
    elif http_status in {401, 403}:
        status = DTERecord.STATUS_REJECTED
    elif response.get("offline") or http_status >= 500:
        status = DTERecord.STATUS_PENDING
    else:
        status = DTERecord.STATUS_PENDING

    error = response.get("error") or {}
    response_text = str(response.get("response_text") or response.get("raw") or "")
    if not response_text and isinstance(response.get("response_body"), str):
        response_text = response.get("response_body") or ""
    error_message = (
        error.get("message")
        or rh.get("descripcionMsg")
        or ""
    )

    return {
        "status": status,
        "hacienda_uuid": parsed_receipt.get("hacienda_uuid") or response.get("uuid") or rh.get("codigoGeneracion") or "",
        "sello_recepcion": parsed_receipt.get("sello_recibido") or rh.get("selloRecibido") or "",
        "sello_recibido": parsed_receipt.get("sello_recibido") or rh.get("selloRecibido") or "",
        "firma": parsed_receipt.get("firma") or "",
        "recibido_at": parsed_receipt.get("recibido_at"),
        "estado_mh": parsed_receipt.get("estado_mh") or rh.get("estado") or "",
        "hacienda_state": parsed_receipt.get("hacienda_state") or rh.get("estado") or "",
        "error_code": str(error.get("codigo_msg") or ""),
        "error_message": str(error_message),
        "response_text": response_text,
    }


def send_dte_for_order(order, payment=None, force: bool = False, queue_only: bool = False) -> DTERecord:
    from apps.dte.services.orchestrator import transmit_sale_dte

    return transmit_sale_dte(
        order.id,
        source="normal_send",
        force=force,
        payment_id=getattr(payment, "id", None),
        queue_only=queue_only,
    )


def send_dte_for_credit_note(credit_note: CreditNote) -> DTERecord:
    order = credit_note.order
    from apps.dte.services.control import build_generation_code, next_control_number

    control_number = next_control_number(order, dte_type="NC_05")
    generation_code = build_generation_code()
    payload = {
        "dte": {
            "identificacion": {
                "tipoDte": "05",
                "numeroControl": control_number,
                "codigoGeneracion": generation_code,
            },
            "resumen": {"totalPagar": str(credit_note.total)},
            "extension": {"motivo": credit_note.motivo},
            "cuerpoDocumento": credit_note.items or [],
        }
    }
    response = send_to_bridge("NC_05", payload, branch_name=order.branch.name, order_id=order.id, branch_id=order.branch_id)
    parsed = interpret_dte_response(response)
    return DTERecord.objects.create(
        order=order,
        payment=None,
        branch=order.branch,
        credit_note=credit_note,
        dte_type="NC_05",
        status=parsed["status"],
        control_number=control_number,
        generation_code=generation_code,
        codigo_generacion=generation_code,
        request_payload=payload,
        response_payload=response if isinstance(response, dict) else {},
        response_text=parsed.get("response_text", ""),
        attempts=1,
        send_attempts=1,
        hacienda_uuid=parsed.get("hacienda_uuid", ""),
        sello_recibido=parsed.get("sello_recibido", ""),
        firma=parsed.get("firma", ""),
        hacienda_state=parsed.get("hacienda_state", ""),
        estado_mh=parsed.get("estado_mh", ""),
        error_code=parsed.get("error_code", ""),
        error_message=parsed.get("error_message", ""),
        last_error_code=parsed.get("error_code", ""),
        last_error_message=parsed.get("error_message", ""),
    )


def build_invalidation_payload(record: DTERecord, motivo: str, responsable_dui: str, solicitante_dui: str, extra: dict[str, Any] | None = None) -> dict:
    payload = {
        "dte": {
            "identificacion": {
                "tipoDte": "AN",
                "numeroControl": record.control_number,
                "codigoGeneracion": record.generation_code or record.codigo_generacion,
            },
            "motivo": motivo,
            "responsable": responsable_dui,
            "solicitante": solicitante_dui,
            "extra": extra or {},
        }
    }
    return payload


def invalidate_dte_for_order(order, motivo: str, responsable_dui: str, solicitante_dui: str, **kwargs) -> dict:
    record = order.dte_records.filter(status=DTERecord.STATUS_ACCEPTED).order_by("-id").first()
    if not record:
        raise DTEPreflightError("No existe DTE aceptado para invalidar")
    payload = build_invalidation_payload(record, motivo, responsable_dui, solicitante_dui, kwargs)
    response = send_to_bridge("INVALIDACION", payload, branch_name=order.branch.name, order_id=order.id, branch_id=order.branch_id)
    parsed = interpret_dte_response(response)
    attempt = DteInvalidationAttempt.objects.create(
        order=order,
        tipo_dte=record.dte_type,
        payload_request=payload,
        payload_response=json.dumps(response, ensure_ascii=False, default=str),
        provider_status=int(response.get("http_status") or 0) if isinstance(response, dict) else None,
        provider_body=response if isinstance(response, dict) else {"raw": str(response)},
        cf_ray=str((response or {}).get("cf-ray") or (response or {}).get("cf_ray") or ""),
        success=parsed["status"] == DTERecord.STATUS_ACCEPTED,
        error_type=str(((response or {}).get("error") or {}).get("type") or ""),
        error_message=parsed.get("error_message", ""),
    )
    if attempt.success:
        record.status = DTERecord.STATUS_INVALIDATED
        record.save(update_fields=["status", "updated_at"])
    return {"attempt_id": attempt.id, "success": attempt.success, "status": parsed["status"]}
