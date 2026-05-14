from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

from django.http import HttpResponse

from apps.dte.models import DTERecord

logger = logging.getLogger(__name__)

SPANISH_MONTHS = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

EXPORT_TYPES = {"json", "f07", "pdf"}
ACCEPTED_STATES = {"ACEPTADO", "RECIBIDO", "PROCESADO", "TRANSMITIDO"}
REJECTED_STATES = {
    "RECHAZADO",
    "PENDIENTE",
    "ENVIANDO",
    "ERROR",
    "FALLIDO",
    "FAILED",
    "NO ENVIADO",
    "NO_ENVIADO",
    "EN_COLA",
    "CREADO",
    "BORRADOR",
    "DRAFT",
    "PENDING",
    "SENDING",
    "REJECTED",
}
SECRET_KEY_RE = re.compile(r"(authorization|token|api[_-]?key|password|passwd|secret|cert|certificate|private[_-]?key|cookie|llave)", re.I)
INVISIBLE_RE = re.compile(r"[\ufeff\u200b\u200c\u200d\u2060]")


@dataclass
class HaciendaResponse:
    estado: str = ""
    selloRecibido: str = ""
    fhProcesamiento: str = ""
    codigoMsg: str = ""
    descripcionMsg: str = ""
    observaciones: list[Any] = field(default_factory=list)
    raw: Any = field(default_factory=dict)


def get_export_zip_name(month: int, year: int, export_type: str) -> str:
    type_lower = str(export_type or "").lower()
    month_name = SPANISH_MONTHS[int(month)]
    return f"{month_name}_{type_lower}_{int(year)}.zip"


def _safe_get(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        if current is None:
            return None
        if isinstance(current, dict):
            if key in current:
                current = current[key]
                continue
            lowered = {str(k).lower(): k for k in current.keys()}
            actual = lowered.get(key.lower())
            current = current.get(actual) if actual is not None else None
        else:
            current = getattr(current, key, None)
    return current


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return ""


def _nested_candidates(dte: DTERecord) -> list[Any]:
    candidates: list[Any] = []
    for value in [
        getattr(dte, "mh_response_json", None),
        getattr(dte, "response_payload", None),
        getattr(dte, "response", None),
        getattr(dte, "respuesta_hacienda", None),
        getattr(dte, "respuestaHacienda", None),
    ]:
        if value:
            candidates.append(value)
            for key in ["respuesta_hacienda", "respuestaHacienda", "responseMh", "respuestaMH", "hacienda", "response_json"]:
                nested = _safe_get(value, key)
                if nested:
                    candidates.append(nested)
    order = getattr(dte, "order", None)
    for log in list(getattr(order, "_prefetched_objects_cache", {}).get("dte_transmissions", [])) if order else []:
        if log.response_body:
            candidates.append(log.response_body)
    for outbox in list(getattr(dte, "_prefetched_objects_cache", {}).get("outbox_entries", [])):
        if outbox.response_body:
            try:
                candidates.append(json.loads(outbox.response_body))
            except Exception:
                pass
    return candidates


def extract_hacienda_response(dte: DTERecord) -> HaciendaResponse:
    candidates = _nested_candidates(dte)
    estado = _first_value(getattr(dte, "estado_mh", ""), getattr(dte, "hacienda_state", ""), getattr(dte, "status", ""))
    sello = _first_value(getattr(dte, "sello_recibido", ""), getattr(dte, "sello_recepcion", ""))
    fh = _first_value(getattr(dte, "hacienda_processed_at", None), getattr(dte, "recibido_at", None))
    codigo_msg = ""
    descripcion_msg = ""
    observaciones: Any = []
    raw: Any = {}
    for candidate in candidates:
        if not raw:
            raw = candidate
        estado = _first_value(_safe_get(candidate, "estado"), _safe_get(candidate, "status"), _safe_get(candidate, "estadoMh"), estado)
        sello = _first_value(
            _safe_get(candidate, "selloRecibido"),
            _safe_get(candidate, "sello_recibido"),
            _safe_get(candidate, "selloRecepcion"),
            _safe_get(candidate, "sello_recepcion"),
            sello,
        )
        fh = _first_value(
            _safe_get(candidate, "fhProcesamiento"),
            _safe_get(candidate, "fechaProcesamiento"),
            _safe_get(candidate, "fecha_procesamiento"),
            fh,
        )
        codigo_msg = _first_value(_safe_get(candidate, "codigoMsg"), _safe_get(candidate, "codigo_msg"), codigo_msg)
        descripcion_msg = _first_value(_safe_get(candidate, "descripcionMsg"), _safe_get(candidate, "descripcion_msg"), _safe_get(candidate, "mensaje"), descripcion_msg)
        candidate_observaciones = _safe_get(candidate, "observaciones")
        if candidate_observaciones:
            observaciones = candidate_observaciones
    if isinstance(fh, datetime):
        fh = fh.isoformat()
    return HaciendaResponse(
        estado=str(estado or "").upper(),
        selloRecibido=str(sello or ""),
        fhProcesamiento=str(fh or ""),
        codigoMsg=str(codigo_msg or ""),
        descripcionMsg=str(descripcion_msg or ""),
        observaciones=observaciones if isinstance(observaciones, list) else [observaciones],
        raw=raw or {},
    )


def normalize_dte_status(dte: DTERecord) -> str:
    response = extract_hacienda_response(dte)
    status_values = [getattr(dte, "status", ""), getattr(dte, "estado_mh", ""), getattr(dte, "hacienda_state", ""), response.estado]
    normalized = [str(value or "").strip().upper().replace("-", "_") for value in status_values if str(value or "").strip()]
    if "INVALIDADO" in normalized:
        return "INVALIDADO"
    if any(value in REJECTED_STATES for value in normalized):
        return next(value for value in normalized if value in REJECTED_STATES)
    if any(value in ACCEPTED_STATES for value in normalized):
        return "ACEPTADO"
    if response.selloRecibido and response.fhProcesamiento and any(value == "TRANSMITIDO" for value in normalized):
        return "ACEPTADO"
    return normalized[0] if normalized else ""


def get_generation_code(dte: DTERecord) -> str:
    return str(_first_value(getattr(dte, "codigo_generacion", ""), getattr(dte, "generation_code", ""), _safe_get(dte.request_payload, "identificacion", "codigoGeneracion"))).upper()


def get_control_number(dte: DTERecord) -> str:
    return str(_first_value(getattr(dte, "control_number", ""), _safe_get(dte.request_payload, "identificacion", "numeroControl")))


def get_tipo_dte(dte: DTERecord) -> str:
    raw = str(_first_value(_safe_get(dte.request_payload, "identificacion", "tipoDte"), getattr(dte, "dte_type", ""))).upper()
    if raw in {"01", "03", "05", "06", "14"}:
        return raw
    if raw.startswith("CF"):
        return "01"
    if raw.startswith("CCF"):
        return "03"
    if raw.startswith("NC"):
        return "05"
    if raw.startswith("ND"):
        return "06"
    if raw.startswith("SE") or raw.startswith("SX"):
        return "14"
    return raw


def dte_folder(dte: DTERecord) -> str:
    if normalize_dte_status(dte) == "INVALIDADO":
        return "INVALIDADOS"
    return {"01": "CF", "03": "CCF", "05": "NC", "06": "ND", "14": "SX"}.get(get_tipo_dte(dte), get_tipo_dte(dte) or "OTROS")


def is_exportable_dte(dte: DTERecord) -> bool:
    status = normalize_dte_status(dte)
    response = extract_hacienda_response(dte)
    code = get_generation_code(dte)
    control = get_control_number(dte)
    tipo = get_tipo_dte(dte)
    if status == "INVALIDADO":
        return bool(code and control and tipo and response.selloRecibido)
    if status == "ACEPTADO":
        return bool(code and response.selloRecibido)
    return False


def _strip_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        clean = {}
        for key, inner in value.items():
            if SECRET_KEY_RE.search(str(key)):
                continue
            clean[key] = _strip_secrets(inner)
        return clean
    if isinstance(value, list):
        return [_strip_secrets(item) for item in value]
    return value


def _hacienda_dict(response: HaciendaResponse) -> dict[str, Any]:
    return {
        "estado": response.estado,
        "selloRecibido": response.selloRecibido,
        "fhProcesamiento": response.fhProcesamiento,
        "codigoMsg": response.codigoMsg,
        "descripcionMsg": response.descripcionMsg,
        "observaciones": response.observaciones,
    }


def _json_export_payload(dte: DTERecord, year: int, month: int) -> dict[str, Any]:
    response = extract_hacienda_response(dte)
    payload = {
        "metadata": {
            "system": "Pico de Gallo POS",
            "export_type": "json",
            "year": year,
            "month": month,
            "tipo_dte": get_tipo_dte(dte),
            "numero_control": get_control_number(dte),
            "codigo_generacion": get_generation_code(dte),
            "estado": normalize_dte_status(dte),
            "fecha_emision": str(getattr(dte, "issue_date", "") or ""),
            "fecha_procesamiento": response.fhProcesamiento,
            "sello_recibido": response.selloRecibido,
        },
        "dte": _strip_secrets(getattr(dte, "request_payload", {}) or {}),
        "respuesta_hacienda": _hacienda_dict(response),
    }
    firma = _first_value(getattr(dte, "firma", ""), _safe_get(dte.response_payload, "firmaElectronica"), _safe_get(dte.request_payload, "firmaElectronica"))
    if firma:
        payload["firmaElectronica"] = firma
    if normalize_dte_status(dte) == "INVALIDADO":
        payload["respuesta_invalidacion"] = _strip_secrets(getattr(dte, "response_payload", {}) or {})
    return payload


def sanitize_csv_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = INVISIBLE_RE.sub("", text)
    text = text.replace("\r", " ").replace("\n", " ").replace(";", ",")
    return re.sub(r"\s+", " ", text).strip()


def format_date_for_hacienda(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        year, month, day = match.groups()
        return f"{day}/{month}/{year}"
    match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", text)
    if match:
        return text
    return text


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value if value is not None and value != "" else "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def format_money_for_f07(value: Any) -> str:
    return str(_decimal(value).copy_abs().quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_csv_without_bom(rows: list[list[Any]]) -> str:
    return "\n".join(";".join(sanitize_csv_value(value) for value in row) for row in rows)


def validate_no_bom(csv: str) -> None:
    if csv.startswith("\ufeff") or "\ufeff" in csv or "\u200b" in csv:
        raise ValueError("CSV contiene BOM o caracteres invisibles no permitidos.")


def _remove_guiones(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "")


def _issue_key(dte: DTERecord) -> tuple[str, str, int]:
    issue = getattr(dte, "issue_date", None) or getattr(dte, "created_at", None)
    return (format_date_for_hacienda(issue), str(getattr(dte, "created_at", "")), int(getattr(dte, "id", 0) or 0))


def _amounts(dte: DTERecord) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    order = getattr(dte, "order", None)
    total = _decimal(getattr(dte, "total_amount", None) or getattr(order, "total", None))
    tax = _decimal(getattr(order, "tax", None))
    subtotal = _decimal(getattr(order, "subtotal", None))
    if not subtotal and total and tax:
        subtotal = total - tax
    if not tax and total and get_tipo_dte(dte) in {"03", "05", "06"}:
        tax = (total - (total / Decimal("1.13"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal = total - tax
    exentas = Decimal("0")
    no_sujetas = Decimal("0")
    return total, subtotal, tax, exentas + no_sujetas


def _customer_doc(dte: DTERecord) -> tuple[str, str]:
    customer = getattr(getattr(dte, "order", None), "customer", None)
    nit_or_nrc = _first_value(getattr(dte, "receiver_nit", ""), getattr(customer, "nit", ""), getattr(customer, "nrc", ""), _safe_get(dte.request_payload, "receptor", "nit"), _safe_get(dte.request_payload, "receptor", "nrc"))
    dui = _first_value(getattr(customer, "dui", ""), _safe_get(dte.request_payload, "receptor", "numDocumento"))
    nit_or_nrc = _remove_guiones(str(nit_or_nrc))
    dui = _remove_guiones(str(dui)) if not nit_or_nrc else ""
    return nit_or_nrc, dui


def _build_cf_rows(records: list[DTERecord]) -> list[list[Any]]:
    grouped: dict[str, list[DTERecord]] = defaultdict(list)
    for dte in records:
        grouped[format_date_for_hacienda(dte.issue_date)].append(dte)
    rows = []
    for fecha in sorted(grouped):
        day_records = sorted(grouped[fecha], key=_issue_key)
        total = sum((_amounts(dte)[0] for dte in day_records), Decimal("0"))
        rows.append([
            fecha,
            "4",
            "01",
            "N/A",
            "N/A",
            "N/A",
            "N/A",
            get_generation_code(day_records[0]),
            get_generation_code(day_records[-1]),
            "",
            "0.00",
            "0.00",
            "0.00",
            format_money_for_f07(total),
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            "0.00",
            format_money_for_f07(total),
            "1",
            "3",
            "2",
        ])
    return rows


def _build_ccf_rows(records: list[DTERecord]) -> list[list[Any]]:
    rows = []
    for dte in sorted(records, key=_issue_key):
        response = extract_hacienda_response(dte)
        total, subtotal, tax, _ = _amounts(dte)
        h, q = _customer_doc(dte)
        rows.append([
            format_date_for_hacienda(dte.issue_date),
            "4",
            get_tipo_dte(dte),
            _remove_guiones(get_control_number(dte)),
            response.selloRecibido,
            _remove_guiones(get_generation_code(dte)),
            "",
            h,
            getattr(dte, "receiver_name", "") or _safe_get(dte.request_payload, "receptor", "nombre") or "",
            "0.00",
            "0.00",
            format_money_for_f07(subtotal),
            format_money_for_f07(tax),
            "0.00",
            "0.00",
            format_money_for_f07(total),
            q,
            "1",
            "3",
            "1",
        ])
    return rows


def _build_invalid_rows(records: list[DTERecord]) -> list[list[Any]]:
    rows = []
    for dte in sorted(records, key=_issue_key):
        response = extract_hacienda_response(dte)
        rows.append([
            get_control_number(dte),
            "4",
            "0",
            "0",
            get_tipo_dte(dte),
            "D",
            response.selloRecibido,
            "0",
            "0",
            get_generation_code(dte),
        ])
    return rows


def _build_sx_rows(records: list[DTERecord]) -> list[list[Any]]:
    rows = []
    for dte in sorted(records, key=_issue_key):
        response = extract_hacienda_response(dte)
        total, _, _, _ = _amounts(dte)
        customer = getattr(getattr(dte, "order", None), "customer", None)
        doc = _remove_guiones(str(_first_value(getattr(customer, "nit", ""), getattr(customer, "dui", ""), getattr(dte, "receiver_nit", ""))))
        if not doc:
            continue
        rows.append([
            "14",
            doc,
            getattr(dte, "receiver_name", "") or getattr(customer, "name", "") or "",
            format_date_for_hacienda(dte.issue_date),
            response.selloRecibido,
            _remove_guiones(get_generation_code(dte)),
            format_money_for_f07(total),
            "0.00",
            "1",
            "1",
            "1",
            "3",
            "5",
        ])
    return rows


def _add_csv(zf: zipfile.ZipFile, name: str, rows: list[list[Any]], columns: int) -> int:
    if not rows:
        return 0
    bad = [idx + 1 for idx, row in enumerate(rows) if len(row) != columns]
    if bad:
        raise ValueError(f"{name} tiene filas con columnas inválidas: {bad}")
    csv = build_csv_without_bom(rows)
    validate_no_bom(csv)
    if not csv.strip():
        return 0
    zf.writestr(name, csv.encode("utf-8"))
    return len(rows)


def _records_for_period(year: int, month: int) -> list[DTERecord]:
    return list(
        DTERecord.objects.select_related("order", "order__customer")
        .prefetch_related("order__dte_transmissions", "outbox_entries")
        .filter(issue_date__year=year, issue_date__month=month)
        .order_by("issue_date", "created_at", "id")
    )


def build_dte_export_zip(year: int, month: int, export_type: str, user: Any = None) -> tuple[bytes, str, dict[str, Any]]:
    export_type = str(export_type or "").lower()
    if export_type not in {"json", "f07"}:
        raise NotImplementedError("PDF export not implemented yet")
    records = _records_for_period(year, month)
    exportable = [dte for dte in records if is_exportable_dte(dte)]
    excluded = len(records) - len(exportable)
    if not exportable:
        raise ValueError("No hay DTE aceptados/recibidos o invalidados válidos para ese período.")

    buffer = io.BytesIO()
    stats = {"exported": 0, "by_type": defaultdict(int), "invalidated": 0, "excluded": excluded, "warnings": []}
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if export_type == "json":
            for dte in exportable:
                code = get_generation_code(dte)
                if not code:
                    stats["warnings"].append(f"DTE sin código generación omitido id={dte.id}")
                    continue
                folder = dte_folder(dte)
                payload = _json_export_payload(dte, year, month)
                zf.writestr(f"{folder}/{code}.json", json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
                stats["exported"] += 1
                stats["by_type"][folder] += 1
                if folder == "INVALIDADOS":
                    stats["invalidated"] += 1
        else:
            accepted = [dte for dte in exportable if normalize_dte_status(dte) != "INVALIDADO"]
            invalidated = [dte for dte in exportable if normalize_dte_status(dte) == "INVALIDADO"]
            cf_rows = _build_cf_rows([dte for dte in accepted if get_tipo_dte(dte) == "01"])
            ccf_rows = _build_ccf_rows([dte for dte in accepted if get_tipo_dte(dte) in {"03", "05", "06"}])
            invalid_rows = _build_invalid_rows(invalidated)
            sx_rows = _build_sx_rows([dte for dte in accepted if get_tipo_dte(dte) == "14"])
            suffix = f"{year}_{month:02d}"
            stats["exported"] += _add_csv(zf, f"CF_OFICIAL_{suffix}.csv", cf_rows, 23)
            stats["exported"] += _add_csv(zf, f"CCF_NC_OFICIAL_{suffix}.csv", ccf_rows, 20)
            stats["exported"] += _add_csv(zf, f"INVALIDADOS_OFICIAL_{suffix}.csv", invalid_rows, 10)
            stats["exported"] += _add_csv(zf, f"SUJETOS_EXCLUIDOS_OFICIAL_{suffix}.csv", sx_rows, 13)
            stats["by_type"].update({"CF": len(cf_rows), "CCF_NC": len(ccf_rows), "INVALIDADOS": len(invalid_rows), "SX": len(sx_rows)})
            stats["invalidated"] = len(invalid_rows)
        if not zf.namelist():
            raise ValueError("No hay archivos DTE válidos para generar en ese período.")
    zip_bytes = buffer.getvalue()
    filename = get_export_zip_name(month, year, export_type)
    if not zip_bytes or not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
        raise ValueError("No se pudo generar el ZIP de exportación DTE.")
    logger.info(
        "dte_export user=%s year=%s month=%s type=%s exported=%s by_type=%s invalidated=%s excluded=%s warnings=%s",
        getattr(user, "id", None), year, month, export_type, stats["exported"], dict(stats["by_type"]), stats["invalidated"], stats["excluded"], stats["warnings"],
    )
    stats["by_type"] = dict(stats["by_type"])
    return zip_bytes, filename, stats


def zip_response(zip_bytes: bytes, filename: str) -> HttpResponse:
    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
