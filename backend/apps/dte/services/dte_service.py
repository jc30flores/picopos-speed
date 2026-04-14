from __future__ import annotations

import json
import logging
import os
import re
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from apps.dte.client import DTEClient
from apps.dte.models import CreditNote, DTERecord, DteInvalidationAttempt
from apps.dte.services.ambiente import normalize_ambiente, resolve_ambiente_with_source
from apps.dte.services.active_branch import get_active_branch
from apps.dte.services.emisor import get_emisor_config, get_emisor_nit
from apps.dte.services.dte_parser import parse_hacienda_response
from apps.dte.services.payment_methods import get_cat017_code_and_label


logger = logging.getLogger(__name__)

TAX_RATE = Decimal("0.13")
TAX_DIVISOR = Decimal("1.13")


def _normalize_ambiente_value(raw: str | None) -> str:
    try:
        return normalize_ambiente(raw)
    except ValueError:
        return "00"


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
    return get_emisor_config()


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


def quantize_money(value: str | int | float | Decimal | None) -> Decimal:
    return money(value)


def calculate_taxable_base_from_gross(gross_amount: Decimal) -> Decimal:
    return _q2(gross_amount / TAX_DIVISOR)


def calculate_iva_from_gross(gross_amount: Decimal) -> Decimal:
    return _q2(gross_amount * TAX_RATE / TAX_DIVISOR)


def _line_charged_total(line: dict) -> Decimal:
    venta_gravada = money(line.get("ventaGravada"))
    venta_exenta = money(line.get("ventaExenta"))
    return money(venta_gravada + venta_exenta)


def _line_expected_total_from_price_discount(line: dict) -> Decimal:
    return money((money(line.get("precioUni")) * money(line.get("cantidad"))) - money(line.get("montoDescu")))


def _is_placeholder_shell(item, paid_mods_total: Decimal) -> bool:
    unit_price = money(item.unit_price)
    return unit_price <= Decimal("0.01") and paid_mods_total > Decimal("0.00")


def calculate_line_tax_breakdown(*, unit_price_gross: Decimal, quantity: Decimal, discount_gross: Decimal, taxable: bool) -> dict[str, Decimal]:
    gross_line_before_discount = _q2(unit_price_gross * quantity)
    discount_gross = _q2(min(gross_line_before_discount, discount_gross))
    gross_line_after_discount = _q2(gross_line_before_discount - discount_gross)

    if taxable:
        if quantity == Decimal("0.00"):
            raise DTEPreflightError("Cantidad inválida (0) para línea gravada.")
        # Regla vigente/aceptada por integración:
        # ventaGravada refleja SIEMPRE el monto final cobrado de la línea (con IVA incluido),
        # tanto con descuento como sin descuento.
        base_unit = _q2(unit_price_gross)
        venta_gravada = gross_line_after_discount
        iva_item = calculate_iva_from_gross(venta_gravada)
        return {
            "precio_uni": base_unit,
            "monto_descu": discount_gross,
            "venta_gravada": venta_gravada,
            "venta_exenta": Decimal("0.00"),
            "iva_item": iva_item,
            "linea_total": venta_gravada,
            "linea_total_objetivo": gross_line_after_discount,
        }

    venta_exenta = gross_line_after_discount
    return {
        "precio_uni": _q2(unit_price_gross),
        "monto_descu": discount_gross,
        "venta_gravada": Decimal("0.00"),
        "venta_exenta": venta_exenta,
        "iva_item": Decimal("0.00"),
        "linea_total": venta_exenta,
        "linea_total_objetivo": venta_exenta,
    }


def _almost_equal(a: Decimal, b: Decimal, tolerance: Decimal = Decimal("0.01")) -> bool:
    return abs(money(a) - money(b)) <= tolerance


def _sum_item_discounts(cuerpo: list[dict]) -> Decimal:
    return money(sum((money(line.get("montoDescu")) for line in cuerpo), Decimal("0.00")))


def _allocate_discount_by_weight(components: list[dict[str, Any]], total_discount: Decimal) -> list[Decimal]:
    target = money(min(total_discount, sum((money(c.get("gross")) for c in components), Decimal("0.00"))))
    if target <= Decimal("0.00"):
        return [Decimal("0.00") for _ in components]
    gross_cents = [to_cents(money(component.get("gross"))) for component in components]
    total_gross_cents = sum(gross_cents)
    if total_gross_cents <= 0:
        return [Decimal("0.00") for _ in components]
    target_cents = to_cents(target)
    raw_alloc = [(target_cents * cents) / total_gross_cents for cents in gross_cents]
    alloc_cents = [int(value) for value in raw_alloc]
    residual = target_cents - sum(alloc_cents)
    remainders = sorted(
        [(idx, raw_alloc[idx] - alloc_cents[idx]) for idx in range(len(alloc_cents))],
        key=lambda item: item[1],
        reverse=True,
    )
    for idx, _ in remainders:
        if residual <= 0:
            break
        alloc_cents[idx] += 1
        residual -= 1
    return [money(Decimal(cents) / Decimal("100")) for cents in alloc_cents]


def _reconcile_line_residual(cuerpo: list[dict[str, Any]], target_total: Decimal, *, taxable: bool, order_id: int | None) -> None:
    emitted_total = money(sum((_line_charged_total(line) for line in cuerpo), Decimal("0.00")))
    residual = money(target_total - emitted_total)
    logger.info("dte.reconciliation.residual_before order_id=%s residual=%s", order_id, residual)
    if residual == Decimal("0.00"):
        logger.info("dte.reconciliation.residual_after order_id=%s residual=%s", order_id, residual)
        return
    candidate = next((line for line in cuerpo if money(line.get("ventaGravada")) > Decimal("0.00")), None)
    if candidate is None and cuerpo:
        candidate = cuerpo[0]
    if candidate is None:
        logger.info("dte.reconciliation.residual_after order_id=%s residual=%s", order_id, residual)
        return
    if taxable and money(candidate.get("ventaGravada")) > Decimal("0.00"):
        adjusted_gross = money(money(candidate.get("ventaGravada")) + residual)
        if adjusted_gross <= Decimal("0.00"):
            return
        candidate["ventaGravada"] = json_number(adjusted_gross)
        candidate["ivaItem"] = json_number(calculate_iva_from_gross(adjusted_gross))
    elif money(candidate.get("ventaExenta")) > Decimal("0.00"):
        adjusted_exempt = money(money(candidate.get("ventaExenta")) + residual)
        if adjusted_exempt <= Decimal("0.00"):
            return
        candidate["ventaExenta"] = json_number(adjusted_exempt)
        candidate["ivaItem"] = json_number(Decimal("0.00"))
    emitted_after = money(sum((_line_charged_total(line) for line in cuerpo), Decimal("0.00")))
    logger.info(
        "dte.reconciliation.residual_after order_id=%s residual=%s",
        order_id,
        money(target_total - emitted_after),
    )


def _validate_dte_totals(dte_payload: dict) -> None:
    resumen = (dte_payload.get("resumen") or {}) if isinstance(dte_payload, dict) else {}
    cuerpo = (dte_payload.get("cuerpoDocumento") or []) if isinstance(dte_payload, dict) else []

    total_no_suj = money(resumen.get("totalNoSuj"))
    total_exenta = money(resumen.get("totalExenta"))
    total_gravada = money(resumen.get("totalGravada"))
    sub_total_ventas = money(resumen.get("subTotalVentas"))
    descu_no_suj = money(resumen.get("descuNoSuj"))
    descu_exenta = money(resumen.get("descuExenta"))
    descu_gravada = money(resumen.get("descuGravada"))
    sub_total = money(resumen.get("subTotal"))
    total_descu = money(resumen.get("totalDescu"))
    total_iva = money(resumen.get("totalIva"))
    monto_total_operacion = money(resumen.get("montoTotalOperacion"))
    total_pagar = money(resumen.get("totalPagar"))
    iva_rete1 = money(resumen.get("ivaRete1"))
    rete_renta = money(resumen.get("reteRenta"))

    sum_line_gravada = Decimal("0.00")
    sum_line_exenta = Decimal("0.00")
    sum_line_iva = Decimal("0.00")
    sum_line_total = Decimal("0.00")
    errors: list[str] = []

    for line in cuerpo:
        qty = money(line.get("cantidad"))
        precio_uni = money(line.get("precioUni"))
        monto_descu_line = money(line.get("montoDescu"))
        venta_gravada_line = money(line.get("ventaGravada"))
        venta_exenta_line = money(line.get("ventaExenta"))
        iva_item_line = money(line.get("ivaItem"))
        num_item = line.get("numItem")

        if venta_gravada_line > Decimal("0.00"):
            charged_calc = _q2((precio_uni * qty) - monto_descu_line)
            calc_venta = charged_calc
            calc_iva = calculate_iva_from_gross(venta_gravada_line)
            line_total = money(venta_gravada_line)
            calc_line_total = money(calc_venta)
            if not _almost_equal(venta_gravada_line, calc_venta):
                errors.append(f"item.{num_item}.ventaGravada={venta_gravada_line} calc={calc_venta}")
            if not _almost_equal(iva_item_line, calc_iva):
                errors.append(f"item.{num_item}.ivaItem={iva_item_line} calc={calc_iva}")
            if not _almost_equal(line_total, calc_line_total):
                errors.append(f"item.{num_item}.lineTotal={line_total} calc={calc_line_total}")

        if venta_exenta_line > Decimal("0.00") and iva_item_line != Decimal("0.00"):
            errors.append(f"item.{num_item}.ivaItem_debe_ser_0_para_exenta={iva_item_line}")

        sum_line_gravada += venta_gravada_line
        sum_line_exenta += venta_exenta_line
        sum_line_iva += iva_item_line
        sum_line_total += money(venta_gravada_line + venta_exenta_line + money(line.get("ventaNoSuj")))

    calc_sub_total_ventas = money(total_no_suj + total_exenta + total_gravada)
    calc_global_desc = money(descu_no_suj + descu_exenta + descu_gravada)
    calc_sub_total = money(calc_sub_total_ventas - calc_global_desc)
    calc_total_descu = money(_sum_item_discounts(cuerpo) + calc_global_desc)
    calc_monto_total_operacion = money(calc_sub_total)
    calc_total_pagar = money(calc_monto_total_operacion - iva_rete1 - rete_renta)

    if not _almost_equal(sub_total_ventas, calc_sub_total_ventas):
        errors.append(f"subTotalVentas={sub_total_ventas} calc={calc_sub_total_ventas}")
    if not _almost_equal(sub_total, calc_sub_total):
        errors.append(f"subTotal={sub_total} calc={calc_sub_total}")
    if not _almost_equal(total_descu, calc_total_descu):
        errors.append(f"totalDescu={total_descu} calc={calc_total_descu}")
    if not _almost_equal(total_gravada, money(sum_line_gravada)):
        errors.append(f"totalGravada={total_gravada} sum_items={money(sum_line_gravada)}")
    if not _almost_equal(total_exenta, money(sum_line_exenta)):
        errors.append(f"totalExenta={total_exenta} sum_items={money(sum_line_exenta)}")
    if not _almost_equal(total_iva, money(sum_line_iva)):
        errors.append(f"totalIva={total_iva} sum_items={money(sum_line_iva)}")
    if not _almost_equal(total_pagar, money(sum_line_total)):
        errors.append(f"totalPagar={total_pagar} sum_lineas={money(sum_line_total)}")
    if not _almost_equal(monto_total_operacion, calc_monto_total_operacion):
        errors.append(f"montoTotalOperacion={monto_total_operacion} calc={calc_monto_total_operacion}")
    if not _almost_equal(total_pagar, calc_total_pagar):
        errors.append(f"totalPagar={total_pagar} calc={calc_total_pagar}")

    if errors:
        logger.error("dte.validation_failed resumen_mismatch %s", " | ".join(errors))
        raise DTEPreflightError("DTE inconsistente: resumen de totales/IVA no cuadra.")


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


def _has_nit_14(value: str | None) -> bool:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return len(digits) == 14


def _resolve_tip_doc(value: str) -> str:
    if _has_real_dui(value):
        return "13"
    if _has_nit_14(value):
        return "36"
    return "13"


def _mask_document(value: str) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) <= 4:
        return "*" * len(digits)
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"


def validate_receptor_payload(receptor: dict[str, Any]) -> None:
    tipo_documento = receptor.get("tipoDocumento")
    num_documento = receptor.get("numDocumento")
    if tipo_documento is None and num_documento is not None:
        raise DTEPreflightError("Si receptor.tipoDocumento es null, receptor.numDocumento también debe ser null")
    for key, value in receptor.items():
        if isinstance(value, str) and not value.strip():
            raise DTEPreflightError(f"receptor.{key} no puede ser string vacío")


def _validate_identificacion_payload(identificacion: dict[str, Any]) -> None:
    ambiente = identificacion.get("ambiente")
    try:
        normalize_ambiente(ambiente)
    except ValueError as exc:
        raise DTEPreflightError(str(exc)) from exc
    tipo_dte = str(identificacion.get("tipoDte") or "").strip()
    if tipo_dte not in {"01", "03", "05", "14", "AN"}:
        raise DTEPreflightError(f"tipoDte inválido: {tipo_dte}")
    if tipo_dte == "AN":
        fec_anula = str(identificacion.get("fecAnula") or "").strip()
        hor_anula = str(identificacion.get("horAnula") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fec_anula):
            raise DTEPreflightError("invalidacion.identificacion.fecAnula es obligatorio (YYYY-MM-DD).")
        if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", hor_anula):
            raise DTEPreflightError("invalidacion.identificacion.horAnula es obligatorio (HH:MM:SS).")
        return
    numero_control = str(identificacion.get("numeroControl") or "").strip()
    if not re.fullmatch(r"DTE-\d{2}-[A-Z0-9]{4}[A-Z0-9]{4}-\d{15}", numero_control):
        logger.error("dte.preflight.invalid_numero_control numeroControl=%s identificacion=%s", numero_control, identificacion)
        raise DTEPreflightError(f"numeroControl inválido: {numero_control}")
    codigo_generacion = str(identificacion.get("codigoGeneracion") or "").strip().upper()
    if not re.fullmatch(r"[A-F0-9-]{36}", codigo_generacion):
        raise DTEPreflightError(f"codigoGeneracion inválido: {codigo_generacion}")


def _validate_emisor_payload(emisor: dict[str, Any]) -> None:
    missing = [k for k in ("nit", "nrc", "nombre", "codActividad", "descActividad") if not emisor.get(k)]
    if missing:
        raise DTEPreflightError(f"Emisor incompleto: faltan {', '.join(missing)}")
    emisor_nit_digits = "".join(ch for ch in str(emisor.get("nit") or "") if ch.isdigit())
    if len(emisor_nit_digits) != 14:
        raise DTEPreflightError(f"NIT emisor inválido: {emisor.get('nit')}")


def _validate_invalidation_emisor_payload(emisor: dict[str, Any]) -> None:
    required = (
        "nit",
        "nombre",
        "tipoEstablecimiento",
        "telefono",
        "correo",
        "codEstable",
        "codPuntoVenta",
        "nomEstablecimiento",
    )
    missing = [k for k in required if not str(emisor.get(k) or "").strip()]
    if missing:
        raise DTEPreflightError(f"invalidacion.emisor incompleto: faltan {', '.join(missing)}")
    prohibited = ("nrc", "codActividad", "descActividad", "nombreComercial")
    prohibited_found = [k for k in prohibited if k in emisor]
    if prohibited_found:
        raise DTEPreflightError(f"invalidacion.emisor contiene campos no permitidos: {', '.join(prohibited_found)}")


def _resolve_non_empty(*candidates: tuple[str, Any]) -> tuple[str, str]:
    for source, value in candidates:
        text = str(value or "").strip()
        if text:
            return text, source
    return "", ""


def _validate_pagos_payload(resumen: dict[str, Any]) -> None:
    pagos = resumen.get("pagos")
    if not isinstance(pagos, list) or not pagos:
        raise DTEPreflightError("resumen.pagos debe contener al menos un pago")
    pagos_total = Decimal("0.00")
    for idx, pago in enumerate(pagos):
        monto = money((pago or {}).get("montoPago"))
        if monto <= Decimal("0.00"):
            raise DTEPreflightError(f"resumen.pagos[{idx}].montoPago inválido: {monto}")
        pagos_total += monto
    total_pagar = money(resumen.get("totalPagar"))
    if not _almost_equal(pagos_total, total_pagar):
        raise DTEPreflightError(f"Suma de pagos ({money(pagos_total)}) no coincide con totalPagar ({total_pagar})")


def validate_dte_preflight_payload(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise DTEPreflightError("Payload DTE inválido: falta objeto dte/invalidacion")
    dte = payload.get("dte")
    if not isinstance(dte, dict):
        dte = payload.get("invalidacion")
    if not isinstance(dte, dict):
        raise DTEPreflightError("Payload DTE inválido: falta objeto dte/invalidacion")
    identificacion = dte.get("identificacion") or {}
    emisor = dte.get("emisor") or {}
    receptor = dte.get("receptor") or {}
    resumen = dte.get("resumen") or {}
    if isinstance(payload.get("invalidacion"), dict):
        ambiente = identificacion.get("ambiente")
        try:
            normalize_ambiente(ambiente)
        except ValueError as exc:
            raise DTEPreflightError(str(exc)) from exc
        fec_anula = str(identificacion.get("fecAnula") or "").strip()
        hor_anula = str(identificacion.get("horAnula") or "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fec_anula):
            raise DTEPreflightError("invalidacion.identificacion.fecAnula es obligatorio (YYYY-MM-DD).")
        if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", hor_anula):
            raise DTEPreflightError("invalidacion.identificacion.horAnula es obligatorio (HH:MM:SS).")
        prohibited_ident = [k for k in ("numeroControl", "tipoDte") if k in identificacion]
        if prohibited_ident:
            raise DTEPreflightError(
                f"invalidacion.identificacion contiene campos no permitidos: {', '.join(prohibited_ident)}"
            )
        documento = dte.get("documento") or {}
        if not isinstance(documento, dict):
            raise DTEPreflightError("invalidacion.documento es obligatorio.")
        missing_documento = [
            key
            for key in ("tipoDocumento", "numDocumento", "codigoGeneracionR", "selloRecibido", "montoIva", "nombre")
            if not str(documento.get(key) or "").strip()
        ]
        if missing_documento:
            raise DTEPreflightError(
                f"invalidacion.documento incompleto: faltan {', '.join(missing_documento)}"
            )
        prohibited_documento = [k for k in ("horEmi",) if k in documento]
        if prohibited_documento:
            raise DTEPreflightError(
                f"invalidacion.documento contiene campos no permitidos: {', '.join(prohibited_documento)}"
            )
        motivo = dte.get("motivo") or {}
        if not isinstance(motivo, dict):
            raise DTEPreflightError("invalidacion.motivo es obligatorio.")
        missing_motivo = [
            key
            for key in (
                "tipoAnulacion",
                "motivoAnulacion",
                "nombreResponsable",
                "tipDocResponsable",
                "numDocResponsable",
                "nombreSolicita",
                "tipDocSolicita",
                "numDocSolicita",
            )
            if not str(motivo.get(key) or "").strip()
        ]
        if missing_motivo:
            raise DTEPreflightError(f"invalidacion.motivo incompleto: faltan {', '.join(missing_motivo)}")
        _validate_invalidation_emisor_payload(emisor)
        prohibited_root = [k for k in ("responsable", "solicitante", "extra") if k in dte]
        if prohibited_root:
            raise DTEPreflightError(
                f"invalidacion contiene campos no permitidos: {', '.join(prohibited_root)}"
            )
        assert_no_string_numbers(payload)
        return
    if str(identificacion.get("tipoDte") or "").strip().upper() == "AN":
        raise DTEPreflightError("Payload legacy inválido: use wrapper 'invalidacion' (no 'dte') para anulaciones.")
    _validate_identificacion_payload(identificacion)
    _validate_emisor_payload(emisor)
    validate_receptor_payload(receptor)
    _validate_pagos_payload(resumen)
    _validate_dte_totals(dte)
    assert_no_string_numbers(payload)


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
        if method_code.strip().lower().replace("-", "_") == "pedidos_ya" and code in {"02", "03"}:
            logger.info("dte.payment_method_mapping pedidos_ya=>card code=%s payment_id=%s", code, getattr(payment, "id", None))
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
    ambiente = _normalize_ambiente_value(ambiente)
    active_branch = get_active_branch()
    final_nit = get_emisor_nit()
    logger.info("[DTE DEBUG] Emisor NIT final utilizado=%s branch_id=%s", final_nit, active_branch.id)
    print(f"[DTE DEBUG] Emisor NIT final utilizado={final_nit}")
    required_emisor = ["nit", "nrc", "nombre", "nombreComercial", "codActividad", "descActividad"]
    missing = [k for k in required_emisor if not emisor.get(k)]
    if missing:
        warn = f"[DTE] WARNING emisor incompleto para branch={active_branch.id}: missing={','.join(missing)}"
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

    commercial_groups: list[dict[str, Any]] = []
    placeholder_items_detected: list[int] = []
    ledger_lines: list[dict[str, Any]] = []
    for item in order.items.select_related("product").prefetch_related("applied_modifiers"):
        quantity = money(item.quantity)
        base_gross = money(money(item.unit_price) * quantity)
        components: list[dict[str, Any]] = [
            {
                "codigo": item.snapshot_sku_or_code or (f"PROD-{item.product_id}" if item.product_id else f"MANUAL-{item.id}"),
                "descripcion": item.name or "ITEM",
                "quantity": quantity,
                "gross": base_gross,
            }
        ]
        paid_mods_total = Decimal("0.00")
        free_mods: list[str] = []
        for mod in item.applied_modifiers.all():
            mod_price = money(mod.modifier_price_snapshot)
            if mod_price > Decimal("0.00"):
                mod_gross = money(mod_price * quantity)
                paid_mods_total += mod_gross
                components.append(
                    {
                        "codigo": f"MOD-{item.id}-{mod.id or len(components)}",
                        "descripcion": f"EXTRA: {mod.modifier_name_snapshot}",
                        "quantity": quantity,
                        "gross": mod_gross,
                    }
                )
            else:
                free_mods.append(mod.modifier_name_snapshot)
        if free_mods:
            components[0]["descripcion"] = f"{components[0]['descripcion']} ({', '.join(free_mods)})"
        group_gross = money(sum((money(c["gross"]) for c in components), Decimal("0.00")))
        discounts = _allocate_discount_by_weight(components, money(item.discount_amount))
        is_shell = _is_placeholder_shell(item, paid_mods_total)
        if is_shell:
            placeholder_items_detected.append(item.id)
        for idx, component in enumerate(components):
            component_discount = discounts[idx]
            ledger_lines.append(
                {
                    "codigo": component["codigo"],
                    "descripcion": component["descripcion"],
                    "quantity": component["quantity"],
                    "gross": money(component["gross"]),
                    "discount": money(component_discount),
                }
            )
        commercial_groups.append(
            {
                "order_item_id": item.id,
                "placeholder_shell": is_shell,
                "gross_before_discount": group_gross,
                "discount_original": money(item.discount_amount),
                "discount_allocated": money(sum(discounts, Decimal("0.00"))),
                "components": len(components),
            }
        )

    for fee in order.fees.all():
        fee_name = (fee.fee_name or "CARGO").strip()[:200]
        fee_qty = money(fee.quantity or 1)
        fee_unit = money(fee.unit_amount if fee.unit_amount is not None else (money(fee.total_amount) / fee_qty))
        fee_total = money(fee.total_amount)
        if not _almost_equal(money(fee_unit * fee_qty), fee_total):
            fee_unit = money(fee_total / fee_qty) if fee_qty > Decimal("0.00") else fee_total
        fee_calc = calculate_line_tax_breakdown(
            unit_price_gross=fee_unit,
            quantity=fee_qty,
            discount_gross=Decimal("0.00"),
            taxable=not order.iva_exempt,
        )
        total_gravada += fee_calc["venta_gravada"]
        total_exenta += fee_calc["venta_exenta"]
        total_iva += fee_calc["iva_item"]
        cuerpo.append({
            "numItem": num_item,
            "tipoItem": 1,
            "codigo": f"FEE-{(fee.fee_type or 'GEN').strip().upper()}-{num_item}",
            "descripcion": fee_name,
            "cantidad": json_number(fee_qty),
            "uniMedida": 59,
            "precioUni": json_number(fee_calc["precio_uni"]),
            "montoDescu": json_number(fee_calc["monto_descu"]),
            "ventaNoSuj": json_number(Decimal("0.00")),
            "ventaExenta": json_number(fee_calc["venta_exenta"]),
            "ventaGravada": json_number(fee_calc["venta_gravada"]),
            "tributos": None,
            "psv": json_number(Decimal("0.00")),
            "noGravado": json_number(Decimal("0.00")),
            "ivaItem": json_number(fee_calc["iva_item"]),
            "codTributo": None,
            "numeroDocumento": None,
            "_lineaObjetivo": json_number(fee_calc["linea_total_objetivo"]),
        })
        num_item += 1
        commercial_groups.append(
            {
                "fee_id": fee.id,
                "fee_type": fee.fee_type,
                "gross_before_discount": fee_total,
                "discount_allocated": Decimal("0.00"),
                "components": 1,
            }
        )

    for ledger in ledger_lines:
        qty = money(ledger["quantity"])
        gross = money(ledger["gross"])
        discount = money(ledger["discount"])
        if qty <= Decimal("0.00") or gross <= Decimal("0.00"):
            continue
        line_calc = calculate_line_tax_breakdown(
            unit_price_gross=money(gross / qty),
            quantity=qty,
            discount_gross=discount,
            taxable=not order.iva_exempt,
        )
        total_gravada += line_calc["venta_gravada"]
        total_exenta += line_calc["venta_exenta"]
        total_iva += line_calc["iva_item"]
        total_descuento += line_calc["monto_descu"]
        cuerpo.append(
            {
                "numItem": num_item,
                "tipoItem": 1,
                "codigo": ledger["codigo"],
                "descripcion": ledger["descripcion"],
                "cantidad": json_number(qty),
                "uniMedida": 59,
                "precioUni": json_number(line_calc["precio_uni"]),
                "montoDescu": json_number(line_calc["monto_descu"]),
                "ventaNoSuj": json_number(Decimal("0.00")),
                "ventaExenta": json_number(line_calc["venta_exenta"]),
                "ventaGravada": json_number(line_calc["venta_gravada"]),
                "tributos": None,
                "psv": json_number(Decimal("0.00")),
                "noGravado": json_number(Decimal("0.00")),
                "ivaItem": json_number(line_calc["iva_item"]),
                "codTributo": None,
                "numeroDocumento": None,
                "_lineaObjetivo": json_number(line_calc["linea_total_objetivo"]),
            }
        )
        num_item += 1

    target_total = money(getattr(order, "total", Decimal("0.00")))
    items_gross_total = Decimal("0.00")
    modifiers_gross_total = Decimal("0.00")
    item_discount_total = Decimal("0.00")
    for item in order.items.prefetch_related("applied_modifiers"):
        qty = money(item.quantity)
        items_gross_total += money(money(item.unit_price) * qty)
        item_discount_total += money(item.discount_amount)
        for mod in item.applied_modifiers.all():
            mod_price = money(mod.modifier_price_snapshot)
            if mod_price > Decimal("0.00"):
                modifiers_gross_total += money(mod_price * qty)
    fees_total = money(sum((money(f.total_amount) for f in order.fees.all()), Decimal("0.00")))
    reconstructed_order_total = money(items_gross_total + modifiers_gross_total + fees_total - item_discount_total)
    logger.info(
        "dte.source_totals order_id=%s order_total=%s items=%s modifiers=%s fees=%s item_discounts=%s reconstructed=%s",
        getattr(order, "id", None),
        target_total,
        money(items_gross_total),
        money(modifiers_gross_total),
        fees_total,
        money(item_discount_total),
        reconstructed_order_total,
    )
    gross_from_lines = Decimal("0.00")
    line_errors: list[str] = []
    for line in cuerpo:
        num_item_line = line.get("numItem")
        line_total = _line_charged_total(line)
        gross_from_lines += line_total
        if money(line.get("ventaGravada")) > Decimal("0.00"):
            iva_calc = calculate_iva_from_gross(money(line.get("ventaGravada")))
            if abs(iva_calc - money(line.get("ivaItem"))) > Decimal("0.01"):
                line_errors.append(
                    f"item.{num_item_line}.ivaItem={money(line.get('ivaItem'))} calc={iva_calc} ventaGravada={money(line.get('ventaGravada'))}"
                )
    gross_from_lines = money(gross_from_lines)
    if line_errors:
        logger.error("dte.line_preflight_failed %s", " | ".join(line_errors))
        raise DTEPreflightError("DTE inconsistente: líneas con IVA/base gravada incompatibles.")

    logger.info(
        "dte.commercial_groups order_id=%s fiscal_rule=precioUni/monto_final+iva13_113 groups=%s placeholders=%s",
        getattr(order, "id", None),
        commercial_groups,
        placeholder_items_detected,
    )
    objective_errors: list[str] = []
    for line in cuerpo:
        line_total = _line_charged_total(line)
        objetivo = money(line.get("_lineaObjetivo"))
        if not _almost_equal(line_total, objetivo):
            objective_errors.append(f"item.{line.get('numItem')}.lineTotal={line_total} objetivo={objetivo}")
        if money(line.get("montoDescu")) > Decimal("0.00"):
            precio_original = money(money(line.get("precioUni")) * money(line.get("cantidad")))
            descuento = money(line.get("montoDescu"))
            venta_gravada = money(line.get("ventaGravada"))
            iva_item = money(line.get("ivaItem"))
            esperado = _line_expected_total_from_price_discount(line)
            serializado = line_total
            if not _almost_equal(esperado, serializado):
                logger.error(
                    "dte.discount_line_mismatch order_id=%s item=%s precio_original=%s descuento=%s total_final_real=%s ventaGravada=%s ivaItem=%s total_serializado=%s diferencia=%s linea_dte=%s",
                    getattr(order, "id", None),
                    line.get("numItem"),
                    precio_original,
                    descuento,
                    esperado,
                    venta_gravada,
                    iva_item,
                    serializado,
                    money(esperado - serializado),
                    line,
                )
                objective_errors.append(f"item.{line.get('numItem')}.discountLineTotal={serializado} esperado={esperado}")
    if objective_errors:
        logger.error("dte.line_preflight_failed %s", " | ".join(objective_errors))
        raise DTEPreflightError("DTE inconsistente: líneas con descuento/final no cuadran.")
    if not _almost_equal(gross_from_lines, target_total):
        _reconcile_line_residual(cuerpo, target_total, taxable=not order.iva_exempt, order_id=getattr(order, "id", None))
        gross_from_lines = money(sum((_line_charged_total(line) for line in cuerpo), Decimal("0.00")))
    if not _almost_equal(gross_from_lines, target_total):
        logger.error(
            "dte.line_total_mismatch order_id=%s fiscal_rule=precioUni/monto_final+iva13_113 groups=%s placeholders=%s total_lineas=%s total_real=%s diff=%s",
            getattr(order, "id", None),
            commercial_groups,
            placeholder_items_detected,
            gross_from_lines,
            target_total,
            money(target_total - gross_from_lines),
        )
        raise DTEPreflightError("DTE inconsistente: suma de líneas no coincide con total real cobrado.")
    for line in cuerpo:
        line.pop("_lineaObjetivo", None)

    total_gravada = money(sum((money(line.get("ventaGravada")) for line in cuerpo), Decimal("0.00")))
    total_exenta = money(sum((money(line.get("ventaExenta")) for line in cuerpo), Decimal("0.00")))
    total_iva = money(sum((money(line.get("ivaItem")) for line in cuerpo), Decimal("0.00")))
    logger.info(
        "dte.final_payload_summary order_id=%s total_lineas=%s total_real=%s total_iva=%s total_desc=%s",
        getattr(order, "id", None),
        gross_from_lines,
        target_total,
        total_iva,
        _sum_item_discounts(cuerpo),
    )
    subtotal_ventas = money(total_gravada + total_exenta)
    global_desc_no_suj = Decimal("0.00")
    global_desc_exenta = Decimal("0.00")
    global_desc_gravada = Decimal("0.00")
    global_desc_total = money(global_desc_no_suj + global_desc_exenta + global_desc_gravada)
    subtotal_final = money(subtotal_ventas - global_desc_total)
    monto_total_operacion = money(subtotal_final)
    total_pagar = target_total
    emisor_payload = {
        "nit": final_nit,
        "nrc": emisor.get("nrc") or "000000",
        "nombre": emisor.get("nombre") or "Pico de Gallo",
        "nombreComercial": emisor.get("nombreComercial") or "Pico de Gallo",
        "codActividad": emisor.get("codActividad") or "56101",
        "descActividad": emisor.get("descActividad") or "Restaurantes y puestos de comidas",
        "tipoEstablecimiento": emisor.get("tipoEstablecimiento") or "02",
        "codEstableMH": emisor.get("codEstableMH") or "X001",
        "codEstable": emisor.get("codEstable") or "X001",
        "codPuntoVentaMH": emisor.get("codPuntoVentaMH") or "X001",
        "codPuntoVenta": emisor.get("codPuntoVenta") or "X001",
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
    nit_value = getattr(customer, "nit", None) or getattr(customer, "num_documento", None)
    has_nit_14 = _has_nit_14(nit_value)
    receptor_tipo_documento = None
    receptor_num_documento = None
    if has_real_dui:
        receptor_tipo_documento = "13"
        receptor_num_documento = _none_if_blank(getattr(customer, "dui", None) or getattr(customer, "num_documento", None))
    elif has_nit_14:
        receptor_tipo_documento = "36"
        receptor_num_documento = "".join(ch for ch in str(nit_value) if ch.isdigit())
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
        "subTotalVentas": json_number(money(subtotal_ventas)), "descuNoSuj": json_number(money(global_desc_no_suj)), "descuExenta": json_number(money(global_desc_exenta)), "descuGravada": json_number(money(global_desc_gravada)),
        "porcentajeDescuento": json_number(Decimal("0.00")), "totalDescu": json_number(money(total_descuento + global_desc_total)), "tributos": None, "subTotal": json_number(money(subtotal_final)),
        "ivaRete1": json_number(Decimal("0.00")), "reteRenta": json_number(Decimal("0.00")), "montoTotalOperacion": json_number(money(monto_total_operacion)), "totalNoGravado": json_number(Decimal("0.00")),
        "totalPagar": json_number(money(total_pagar)), "totalLetras": _number_to_words_es_usd(total_pagar), "totalIva": json_number(money(total_iva if not order.iva_exempt else Decimal("0.00"))),
        "saldoFavor": json_number(Decimal("0.00")), "condicionOperacion": 1,
        "pagos": pagos,
        "numPagoElectronico": None,
    }
    order_total = target_total
    if not _almost_equal(money(resumen["totalPagar"]), order_total):
        diff = money(order_total - money(resumen["totalPagar"]))
        logger.error(
            "dte.financial_mismatch order_id=%s order_total=%s total_pagar=%s diff=%s disposable_total=%s",
            getattr(order, "id", None),
            order_total,
            money(resumen["totalPagar"]),
            diff,
            money(getattr(order, "disposable_total", Decimal("0.00"))),
        )
        raise DTEPreflightError("DTE inconsistente: totalPagar no coincide con total real cobrado.")

    logger.info("dte.tax_rule precioUni/monto_final ventaGravada/monto_final ivaItem=round(ventaGravada*13/113,2)")
    logger.info(
        "dte.financial_compare order_id=%s order_total=%s disposable_total=%s total_pagar_dte=%s total_iva_dte=%s",
        getattr(order, "id", None),
        money(order.total),
        money(getattr(order, "disposable_total", Decimal("0.00"))),
        money(total_pagar),
        money(total_iva),
    )
    for line in cuerpo:
        logger.info(
            "dte.preflight.line numItem=%s cantidad=%s precioUni=%s ventaGravada=%s ventaExenta=%s ivaItem=%s montoDescu=%s",
            line.get("numItem"),
            line.get("cantidad"),
            line.get("precioUni"),
            line.get("ventaGravada"),
            line.get("ventaExenta"),
            line.get("ivaItem"),
            line.get("montoDescu"),
        )

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
    validate_dte_preflight_payload(payload)
    logger.info(
        "dte.preflight.ok ambiente=%s tipoDte=%s receptor_tipoDocumento=%s receptor_numDocumento=%s",
        payload["dte"]["identificacion"].get("ambiente"),
        payload["dte"]["identificacion"].get("tipoDte"),
        payload["dte"]["receptor"].get("tipoDocumento"),
        payload["dte"]["receptor"].get("numDocumento"),
    )
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
    validate_dte_preflight_payload(payload)
    root_key = "invalidacion" if dte_type == "INVALIDACION" else "dte"
    ident = payload.get(root_key, {}).get("identificacion", {})
    ambiente = ident.get("ambiente")
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
        print(
            f"[DTE] DTE SEND >>> tipo={dte_type} sucursal={branch_name} ambiente={ambiente} root={root_key} numeroControl={ident.get('numeroControl')} codigoGeneracion={ident.get('codigoGeneracion')}"
        )
        print(payload_pretty)
        return {"success": False, "error": {"message": str(exc), "type": "NETWORK_ERROR"}, "offline": True}

    print(f"[DTE] MH_AMBIENTE={_get_env('MH_AMBIENTE', _get_env('DTE_AMBIENTE', '00'))} DTE_BASE_URL={base_url}")
    print(f"[DTE] DTE ENDPOINT >>> path={DTE_ENDPOINT_BY_TYPE.get(dte_type)} url={url}")
    print(
        f"[DTE] DTE SEND >>> tipo={dte_type} sucursal={branch_name} ambiente={ambiente} root={root_key} numeroControl={ident.get('numeroControl')} codigoGeneracion={ident.get('codigoGeneracion')}"
    )
    print(payload_pretty)
    logger.info("DTE ENDPOINT >>> %s", url)
    logger.info(
        "DTE SEND >>> (tipo=%s, sucursal=%s, ambiente=%s, root=%s, numeroControl=%s, codigoGeneracion=%s)\n%s",
        dte_type,
        branch_name,
        ambiente,
        root_key,
        ident.get("numeroControl"),
        ident.get("codigoGeneracion"),
        payload_pretty,
    )

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
    active_branch = get_active_branch()
    response = send_to_bridge("NC_05", payload, branch_name=active_branch.name, order_id=order.id, branch_id=active_branch.id)
    parsed = interpret_dte_response(response)
    return DTERecord.objects.create(
        order=order,
        payment=None,
        branch=active_branch,
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
    extra = extra or {}
    request_dte = (record.request_payload or {}).get("dte") or {}
    request_identificacion = (
        request_dte.get("identificacion")
        or (record.request_payload or {}).get("identificacion")
        or {}
    )
    numero_control, numero_control_source = _resolve_non_empty(
        ("dte_record.control_number", record.control_number),
        ("request_payload.dte.identificacion.numeroControl", request_identificacion.get("numeroControl")),
    )
    codigo_generacion, codigo_generacion_source = _resolve_non_empty(
        ("dte_record.generation_code", record.generation_code),
        ("dte_record.codigo_generacion", record.codigo_generacion),
        ("request_payload.dte.identificacion.codigoGeneracion", request_identificacion.get("codigoGeneracion")),
    )
    tipo_dte_base, tipo_dte_source = _resolve_non_empty(
        ("request_payload.dte.identificacion.tipoDte", request_identificacion.get("tipoDte")),
        ("dte_record.dte_type", str(record.dte_type or "").split("_")[-1].strip()),
    )
    sello_recibido, sello_source = _resolve_non_empty(
        ("response_payload.respuesta_hacienda.selloRecibido", (record.response_payload or {}).get("respuesta_hacienda", {}).get("selloRecibido")),
        ("dte_record.sello_recibido", record.sello_recibido),
        ("dte_record.sello_recepcion", record.sello_recepcion),
    )
    fec_emi, fec_emi_source = _resolve_non_empty(
        ("request_payload.dte.identificacion.fecEmi", request_identificacion.get("fecEmi")),
        ("dte_record.issue_date", record.issue_date),
    )
    if not numero_control:
        raise DTEPreflightError(
            f"No se pudo resolver numDocumento/numeroControl del DTE base (dte_record_id={record.id})."
        )
    if not codigo_generacion:
        raise DTEPreflightError(
            f"No se pudo resolver codigoGeneracion del DTE base (dte_record_id={record.id})."
        )
    if not sello_recibido:
        raise DTEPreflightError(
            f"No se pudo resolver selloRecibido del DTE base (dte_record_id={record.id})."
        )
    num_doc_responsable, num_doc_responsable_source = _resolve_non_empty(
        ("request.responsable_dui", responsable_dui),
        ("kwargs.numDocResponsable", extra.get("numDocResponsable")),
    )
    if not num_doc_responsable:
        raise DTEPreflightError("No se puede invalidar: falta configurar numDocResponsable")
    num_doc_solicita, num_doc_solicita_source = _resolve_non_empty(
        ("request.solicitante_dui", solicitante_dui),
        ("kwargs.numDocSolicita", extra.get("numDocSolicita")),
    )
    if not num_doc_solicita:
        raise DTEPreflightError("No se puede invalidar: falta configurar numDocSolicita")
    tip_doc_responsable = _resolve_tip_doc(num_doc_responsable)
    tip_doc_solicita = _resolve_tip_doc(num_doc_solicita)
    logger.info(
        "dte.invalidation.document_resolved dte_record_id=%s num_doc_responsable=%s num_doc_solicita=%s tip_doc_responsable=%s tip_doc_solicita=%s",
        record.id,
        _mask_document(num_doc_responsable),
        _mask_document(num_doc_solicita),
        tip_doc_responsable,
        tip_doc_solicita,
    )

    emisor_from_record = request_dte.get("emisor") or {}
    receptor_origen = request_dte.get("receptor") or {}
    resumen_origen = request_dte.get("resumen") or {}
    resolved_emisor_config = _resolve_branch_config(record.order)
    resolved_emisor = {
        "nit": emisor_from_record.get("nit") or get_emisor_nit(),
        "nrc": emisor_from_record.get("nrc") or resolved_emisor_config.get("nrc") or "000000",
        "nombre": emisor_from_record.get("nombre") or resolved_emisor_config.get("nombre") or "Emisor",
        "codActividad": emisor_from_record.get("codActividad") or resolved_emisor_config.get("codActividad") or "56101",
        "descActividad": emisor_from_record.get("descActividad") or resolved_emisor_config.get("descActividad") or "Actividad económica",
        "nombreComercial": emisor_from_record.get("nombreComercial") or resolved_emisor_config.get("nombreComercial") or "Sucursal",
    }

    raw_ambiente, source = resolve_ambiente_with_source()
    ambiente = _normalize_ambiente_value(raw_ambiente)
    missing_emisor_fields = [k for k in ("nit", "nombre") if not resolved_emisor.get(k)]
    if missing_emisor_fields:
        raise DTEPreflightError(f"Emisor incompleto: faltan {', '.join(missing_emisor_fields)}")
    logger.info(
        "dte.invalidation.base_resolved dte_record_id=%s order_id=%s tipo=%s numeroControl=%s codigoGeneracion=%s emisor_original_nit=%s emisor_final_nit=%s ambiente_source=%s ambiente_configured=%s ambiente_resolved=%s",
        record.id,
        getattr(record, "order_id", None),
        tipo_dte_base,
        numero_control,
        codigo_generacion,
        emisor_from_record.get("nit"),
        resolved_emisor.get("nit"),
        source,
        raw_ambiente,
        ambiente,
    )
    now_sv = timezone.now().astimezone(ZoneInfo("America/El_Salvador"))
    emisor_full = {
        "nit": resolved_emisor.get("nit"),
        "nombre": resolved_emisor.get("nombre"),
        "nomEstablecimiento": resolved_emisor_config.get("nomEstablecimiento") or resolved_emisor.get("nombreComercial") or "Sucursal",
        "tipoEstablecimiento": resolved_emisor_config.get("tipoEstablecimiento") or "02",
        "codEstable": resolved_emisor_config.get("codEstable") or "X001",
        "codPuntoVenta": resolved_emisor_config.get("codPuntoVenta") or "X001",
        "telefono": resolved_emisor_config.get("telefono") or "00000000",
        "correo": resolved_emisor_config.get("correo") or "facturas@example.com",
    }
    monto_iva_raw = resumen_origen.get("totalIva")
    if monto_iva_raw in (None, ""):
        raise DTEPreflightError("No se puede invalidar: falta montoIva del DTE original")
    receptor_nombre, receptor_nombre_source = _resolve_non_empty(
        ("request_payload.dte.receptor.nombre", receptor_origen.get("nombre")),
        ("order.customer_name", getattr(record.order, "customer_name", "")),
    )
    documento = {
        "tipoDocumento": tipo_dte_base,
        "numDocumento": numero_control,
        "codigoGeneracionR": codigo_generacion,
        "selloRecibido": sello_recibido,
        "montoIva": str(money(monto_iva_raw)),
        "nombre": receptor_nombre,
        "fecEmi": fec_emi,
    }
    payload = {
        "invalidacion": {
            "identificacion": {
                "version": 2,
                "ambiente": ambiente,
                "codigoGeneracion": str(uuid.uuid4()).upper(),
                "fecAnula": now_sv.date().isoformat(),
                "horAnula": now_sv.strftime("%H:%M:%S"),
            },
            "documento": documento,
            "emisor": emisor_full,
            "motivo": {
                "tipoAnulacion": int((extra or {}).get("tipoAnulacion") or 2),
                "motivoAnulacion": str(motivo or "").strip() or "Invalidación solicitada",
                "nombreResponsable": str(extra.get("nombreResponsable") or "Responsable").strip(),
                "tipDocResponsable": tip_doc_responsable,
                "numDocResponsable": num_doc_responsable,
                "nombreSolicita": str(extra.get("nombreSolicita") or "Solicitante").strip(),
                "tipDocSolicita": tip_doc_solicita,
                "numDocSolicita": num_doc_solicita,
            },
        }
    }
    logger.info(
        "dte.invalidation.field_sources dte_record_id=%s sources=%s",
        record.id,
        {
            "tipoDocumento": tipo_dte_source,
            "numDocumento": numero_control_source,
            "codigoGeneracionR": codigo_generacion_source,
            "selloRecibido": sello_source,
            "montoIva": "request_payload.dte.resumen.totalIva",
            "nombre": receptor_nombre_source,
            "fecEmi": fec_emi_source,
            "emisor.nit": "request_payload.dte.emisor.nit|config",
            "emisor.nombre": "request_payload.dte.emisor.nombre|config",
            "emisor.nomEstablecimiento": "branch_config.nomEstablecimiento|nombreComercial",
            "emisor.tipoEstablecimiento": "branch_config.tipoEstablecimiento",
            "emisor.codEstable": "branch_config.codEstable",
            "emisor.codPuntoVenta": "branch_config.codPuntoVenta",
            "emisor.telefono": "branch_config.telefono",
            "emisor.correo": "branch_config.correo",
            "numDocResponsable": num_doc_responsable_source,
            "numDocSolicita": num_doc_solicita_source,
        },
    )
    logger.info(
        "dte.invalidation.payload_summary dte_record_id=%s order_id=%s identificacion=%s documento_keys=%s emisor_keys=%s motivo_keys=%s",
        record.id,
        getattr(record, "order_id", None),
        payload["invalidacion"]["identificacion"],
        list(payload["invalidacion"]["documento"].keys()),
        list(payload["invalidacion"]["emisor"].keys()),
        list(payload["invalidacion"]["motivo"].keys()),
    )
    logger.info("dte.invalidation.payload_full dte_record_id=%s payload=%s", record.id, payload)
    return payload


def invalidate_dte_for_order(
    order,
    motivo: str,
    responsable_dui: str,
    solicitante_dui: str,
    *,
    dte_record: DTERecord | None = None,
    allow_non_accepted: bool = False,
    **kwargs,
) -> dict:
    record = dte_record or order.dte_records.filter(status=DTERecord.STATUS_ACCEPTED).order_by("-id").first()
    if not record and allow_non_accepted:
        record = order.dte_records.order_by("-id").first()
    if not record:
        raise DTEPreflightError("No existe DTE base para invalidar")
    if record.status == DTERecord.STATUS_INVALIDATED:
        return {
            "attempt_id": None,
            "success": True,
            "status": DTERecord.STATUS_INVALIDATED,
            "error": "",
            "already_invalidated": True,
        }
    payload = build_invalidation_payload(record, motivo, responsable_dui, solicitante_dui, kwargs)
    try:
        validate_dte_preflight_payload(payload)
        logger.info("dte.invalidation.preflight_ok order_id=%s dte_record_id=%s", order.id, record.id)
    except DTEPreflightError:
        logger.exception("dte.invalidation.preflight_failed order_id=%s dte_record_id=%s", order.id, record.id)
        logger.exception("dte.invalidation.schema_error order_id=%s dte_record_id=%s", order.id, record.id)
        raise
    active_branch = get_active_branch()
    response = send_to_bridge("INVALIDACION", payload, branch_name=active_branch.name, order_id=order.id, branch_id=active_branch.id)
    logger.info("dte.invalidation.bridge_response order_id=%s dte_record_id=%s response=%s", order.id, record.id, response)
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
        logger.info("dte.invalidation.success order_id=%s dte_record_id=%s attempt_id=%s", order.id, record.id, attempt.id)
    else:
        logger.error(
            "dte.invalidation.failure order_id=%s dte_record_id=%s attempt_id=%s error=%s",
            order.id,
            record.id,
            attempt.id,
            attempt.error_message,
        )
    logger.info(
        "dte.invalidation.attempt order_id=%s dte_record_id=%s base_status=%s success=%s error=%s",
        order.id,
        record.id,
        record.status,
        attempt.success,
        attempt.error_message,
    )
    return {"attempt_id": attempt.id, "success": attempt.success, "status": parsed["status"], "error": attempt.error_message}
