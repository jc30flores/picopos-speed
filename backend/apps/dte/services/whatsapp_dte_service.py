from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import re
import time

import requests

from apps.dte.services.delivery_payloads import build_delivery_base_payload
from apps.dte.models import DTERecord, DteDeliveryAttempt
from apps.dte.services.delivery_config import resolve_delivery_config
from apps.printing.receipt_pdf import build_receipt_pdf_from_text
from apps.printing.services.renderers import render_customer_ticket

logger = logging.getLogger("apps.dte")
PHONE_RE = re.compile(r"^\d{8,15}$")
INVALID_PHONES = {"00000000", "000000000", "0000000000", "50300000000"}
MAX_LOG_TEXT = 3000


def _normalize_phone(value: str | None) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _mask_phone(value: str | None) -> str:
    digits = _normalize_phone(value)
    if not digits:
        return "***"
    tail = digits[-4:] if len(digits) >= 4 else digits
    return f"***{tail}"


def _is_valid_phone(phone: str) -> bool:
    if not PHONE_RE.match(phone):
        return False
    if phone in INVALID_PHONES or set(phone) == {"0"}:
        return False
    return True


def _mask_secret(value: str | None) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}***{text[-2:]}"


def _sanitize_headers(headers: dict | None) -> dict:
    src = headers or {}
    out = {}
    for key, value in src.items():
        lowered = str(key).lower()
        if lowered in {"authorization", "x-api-key", "api-key"}:
            out[key] = _mask_secret(str(value))
        else:
            out[key] = str(value)
    return out


def _json_compact(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)


def _json_pretty(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _json_for_form(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _json_compact(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sanitize_payload_for_log(payload: dict) -> dict:
    cloned = dict(payload or {})
    if "num_receptor" in cloned:
        cloned["num_receptor"] = _mask_phone(cloned.get("num_receptor"))
    if "num_cliente" in cloned:
        cloned["num_cliente"] = _mask_phone(cloned.get("num_cliente"))
    dte = cloned.get("dte")
    if isinstance(dte, dict):
        receptor = dte.get("receptor") if isinstance(dte.get("receptor"), dict) else {}
        if receptor:
            receptor = {**receptor, "telefono": _mask_phone(receptor.get("telefono"))}
            cloned["dte"] = {**dte, "receptor": receptor}
    return cloned


def _build_whatsapp_files(record: DTERecord, payload: dict) -> tuple[dict, list[dict]]:
    files = {}
    meta = []
    tipo_dte = str(payload.get("tipo_dte") or "01").strip() or "01"
    generation_code = str(payload.get("generation_code") or record.generation_code or record.codigo_generacion or "").strip() or str(record.id)
    invoice_json = payload.get("invoice_json") if isinstance(payload.get("invoice_json"), dict) else {}
    json_payload = invoice_json if invoice_json else {
        "dte": payload.get("dte") if isinstance(payload.get("dte"), dict) else {},
        "respuesta_hacienda": payload.get("respuesta_hacienda") if isinstance(payload.get("respuesta_hacienda"), dict) else {},
    }
    json_bytes = _json_pretty(json_payload).encode("utf-8")
    json_name = f"DTE-{tipo_dte}-{generation_code}.json"
    files["json_file"] = (json_name, json_bytes, "application/json")
    meta.append(
        {"field": "json_file", "name": json_name, "mime": "application/json", "size": len(json_bytes), "sha256": _sha256_hex(json_bytes)}
    )
    try:
        ticket = render_customer_ticket(record.order)
        pdf_result = build_receipt_pdf_from_text(
            text=str(ticket.get("text") or ""),
            filename=f"DTE-{tipo_dte}-{generation_code}.pdf",
            receipt_context=ticket.get("meta", {}).get("receipt_context"),
            center_lines=ticket.get("meta", {}).get("pdf_center_lines"),
        )
        pdf_name = str(pdf_result.filename or f"DTE-{tipo_dte}-{generation_code}.pdf")
        pdf_bytes = bytes(pdf_result.pdf_bytes or b"")
        if pdf_bytes:
            files["pdf_file"] = (pdf_name, pdf_bytes, "application/pdf")
            meta.append(
                {"field": "pdf_file", "name": pdf_name, "mime": "application/pdf", "size": len(pdf_bytes), "sha256": _sha256_hex(pdf_bytes)}
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("WHATSAPP_ATTACHMENTS_PDF_BUILD_FAILED order_id=%s error=%s", record.order_id, exc)
    return files, meta


def _build_whatsapp_form_data(payload: dict) -> dict:
    invoice_json = payload.get("invoice_json") if isinstance(payload.get("invoice_json"), dict) else {}
    respuesta_hacienda = invoice_json.get("respuesta_hacienda") if isinstance(invoice_json.get("respuesta_hacienda"), dict) else {}
    data = {
        "num_receptor": _json_for_form(payload.get("num_receptor")),
        "send_json": _json_for_form(payload.get("send_json")),
        "tipo_dte": _json_for_form(payload.get("tipo_dte")),
        "doc_type": _json_for_form(payload.get("doc_type")),
        "issued_id": _json_for_form(payload.get("issued_id")),
        "order_id": _json_for_form(payload.get("order_id")),
        "generation_code": _json_for_form(payload.get("generation_code")),
        "control_number": _json_for_form(payload.get("control_number")),
        "receiver_name": _json_for_form(payload.get("receiver_name")),
        "estado_mh": _json_for_form(payload.get("estado_mh")),
        "empresa": _json_for_form(payload.get("empresa")),
        "total": _json_for_form(payload.get("total")),
        "dte": _json_for_form(payload.get("dte") if isinstance(payload.get("dte"), dict) else {}),
        "respuesta_hacienda": _json_for_form(respuesta_hacienda),
        "invoice_json": _json_for_form(invoice_json),
    }
    if str(payload.get("num_cliente") or "").strip():
        data["num_cliente"] = _json_for_form(payload.get("num_cliente"))
    return data


def _response_has_job_signal(provider_body: dict, http_status: int) -> bool:
    body = provider_body or {}
    if not (200 <= http_status < 300):
        return False
    if body.get("job_id"):
        return True
    status_text = str(body.get("status") or "").strip().lower()
    if status_text in {"queued", "processing", "sent", "ok"}:
        return True
    message_text = str(body.get("message") or body.get("detail") or "").strip().lower()
    if message_text in {"queued", "processing", "sent", "ok"}:
        return True
    if bool(body.get("queued")):
        return True
    return False


def _validate_whatsapp_payload_contract(payload: dict) -> list[str]:
    missing = []
    if not str(payload.get("num_receptor") or "").strip():
        missing.append("num_receptor")
    if not str(payload.get("empresa") or "").strip():
        missing.append("empresa")
    if not isinstance(payload.get("dte"), dict) or not payload.get("dte"):
        missing.append("dte")
    if payload.get("send_json") is not True:
        missing.append("send_json")
    invoice_json = payload.get("invoice_json")
    if not isinstance(invoice_json, dict):
        missing.append("invoice_json")
    elif not isinstance(invoice_json.get("respuesta_hacienda"), dict):
        missing.append("invoice_json.respuesta_hacienda")
    return missing


def _build_debug_curl(
    *,
    endpoint: str,
    headers: dict,
    payload: dict,
    data: dict | None,
    file_meta: list[dict],
    as_multipart: bool,
) -> str:
    safe_headers = _sanitize_headers(headers)
    parts = [f"curl -X POST '{endpoint}'"]
    for k, v in safe_headers.items():
        parts.append(f"-H '{k}: {v}'")
    if as_multipart:
        for k, v in (data or {}).items():
            parts.append(f"--form '{k}={v}'")
        for item in file_meta:
            parts.append(f"--form '{item['field']}=@{item['name']};type={item['mime']}'")
    else:
        parts.append(f"--data '{_json_compact(_sanitize_payload_for_log(payload))}'")
    return " ".join(parts)


def _log_whatsapp_request_debug(
    *,
    attempt: DteDeliveryAttempt,
    endpoint: str,
    headers: dict,
    payload: dict,
    file_meta: list[dict],
    data: dict | None,
    as_multipart: bool,
) -> None:
    safe_payload = _sanitize_payload_for_log(payload)
    invoice_json = payload.get("invoice_json") if isinstance(payload.get("invoice_json"), dict) else {}
    respuesta_hacienda = invoice_json.get("respuesta_hacienda") if isinstance(invoice_json.get("respuesta_hacienda"), dict) else {}
    misplaced = [
        key
        for key in ("sello_recibido", "selloRecibido", "fh_procesamiento", "fhProcesamiento")
        if key in payload or key in invoice_json
    ]
    logger.info(
        "WHATSAPP_OUTGOING_REQUEST job_id=%s channel=whatsapp issued_id=%s order_id=%s method=POST endpoint=%s content_type=%s headers=%s fields=%s required=%s has_invoice_json=%s has_respuesta_hacienda=%s respuesta_hacienda_keys=%s files=%s payload=%s curl=%s",
        attempt.id,
        payload.get("issued_id"),
        payload.get("order_id"),
        endpoint,
        "multipart/form-data" if as_multipart else "application/json",
        _json_compact(_sanitize_headers(headers)),
        sorted(payload.keys()),
        {
            "num_receptor": bool(payload.get("num_receptor")),
            "empresa": bool(payload.get("empresa")),
            "send_json": payload.get("send_json") is True,
            "dte": isinstance(payload.get("dte"), dict) and bool(payload.get("dte")),
            "respuesta_hacienda": isinstance(respuesta_hacienda, dict),
            "selloRecibido": "selloRecibido" in respuesta_hacienda,
            "sello_recibido": "sello_recibido" in respuesta_hacienda,
            "fhProcesamiento": "fhProcesamiento" in respuesta_hacienda,
            "fh_procesamiento": "fh_procesamiento" in respuesta_hacienda,
            "pdf": any(item["mime"] == "application/pdf" for item in file_meta),
            "json": any(item["mime"] == "application/json" for item in file_meta),
        },
        bool(invoice_json),
        bool(respuesta_hacienda),
        sorted(respuesta_hacienda.keys()),
        file_meta,
        _json_pretty(safe_payload),
        _build_debug_curl(
            endpoint=endpoint,
            headers=headers,
            payload=payload,
            data=data,
            file_meta=file_meta,
            as_multipart=as_multipart,
        ),
    )
    if misplaced:
        logger.warning("WHATSAPP_OUTGOING_REQUEST_MISPLACED_KEYS job_id=%s misplaced=%s", attempt.id, misplaced)


def _log_whatsapp_response_debug(*, attempt: DteDeliveryAttempt, response, provider_body: dict) -> None:
    headers_subset = {
        "content-type": response.headers.get("content-type"),
        "x-request-id": response.headers.get("x-request-id"),
    }
    logger.info(
        "WHATSAPP_INCOMING_RESPONSE job_id=%s status_code=%s headers=%s body=%s parsed=%s",
        attempt.id,
        response.status_code,
        _json_compact({k: v for k, v in headers_subset.items() if v}),
        response.text[:MAX_LOG_TEXT],
        _json_compact(provider_body or {}),
    )
    if 200 <= response.status_code < 300 and not _response_has_job_signal(provider_body or {}, response.status_code):
        logger.warning(
            "WHATSAPP_PROVIDER_2XX_WITHOUT_JOB_SIGNAL job_id=%s status_code=%s body=%s",
            attempt.id,
            response.status_code,
            _json_compact(provider_body or {}),
        )


@dataclass(frozen=True)
class WhatsAppDestinationResolution:
    raw_phone: str
    normalized_phone: str
    source: str
    rejected_reason: str
    is_valid: bool


def resolve_whatsapp_destination(
    record: DTERecord,
    *,
    to_phone: str | None = None,
    allow_default_fallback: bool | None = None,
) -> WhatsAppDestinationResolution:
    config = resolve_delivery_config()
    dte_payload = _safe_dte_for_whatsapp(record)
    receptor_payload = dte_payload.get("receptor") if isinstance(dte_payload.get("receptor"), dict) else {}
    receptor_phone = _normalize_phone(receptor_payload.get("telefono"))
    customer_phone = _normalize_phone(getattr(getattr(record.order, "customer", None), "telefono", ""))
    requested_raw = str(to_phone or "").strip()
    requested_phone = _normalize_phone(requested_raw)
    default_phone = _normalize_phone(config.whatsapp_default_phone)
    fallback_enabled = config.whatsapp_allow_default_fallback if allow_default_fallback is None else bool(allow_default_fallback)

    if requested_raw:
        if not requested_phone:
            return WhatsAppDestinationResolution(
                raw_phone=requested_raw,
                normalized_phone="",
                source="client_phone",
                rejected_reason="Teléfono de cliente inválido para WhatsApp.",
                is_valid=False,
            )
        if not _is_valid_phone(requested_phone):
            return WhatsAppDestinationResolution(
                raw_phone=requested_raw,
                normalized_phone=requested_phone,
                source="client_phone",
                rejected_reason="Teléfono de cliente inválido para WhatsApp.",
                is_valid=False,
            )
        return WhatsAppDestinationResolution(
            raw_phone=requested_raw,
            normalized_phone=requested_phone,
            source="client_phone",
            rejected_reason="",
            is_valid=True,
        )

    if receptor_phone and _is_valid_phone(receptor_phone):
        return WhatsAppDestinationResolution(
            raw_phone=receptor_phone,
            normalized_phone=receptor_phone,
            source="dte_receptor_phone",
            rejected_reason="",
            is_valid=True,
        )

    if customer_phone and _is_valid_phone(customer_phone):
        return WhatsAppDestinationResolution(
            raw_phone=customer_phone,
            normalized_phone=customer_phone,
            source="client_phone",
            rejected_reason="",
            is_valid=True,
        )

    if fallback_enabled and default_phone and _is_valid_phone(default_phone):
        return WhatsAppDestinationResolution(
            raw_phone=default_phone,
            normalized_phone=default_phone,
            source="default_fallback",
            rejected_reason="",
            is_valid=True,
        )

    reason = "Sin teléfono válido (manual o receptor.telefono en DTE)."
    if not fallback_enabled:
        reason = "Sin teléfono válido y fallback por defecto deshabilitado."
    return WhatsAppDestinationResolution(
        raw_phone=requested_raw or customer_phone or default_phone,
        normalized_phone="",
        source="client_phone" if (requested_raw or customer_phone) else "default_fallback",
        rejected_reason=reason,
        is_valid=False,
    )


def validate_whatsapp_target(
    record: DTERecord,
    to_phone: str | None = None,
    *,
    allow_default_fallback: bool | None = None,
) -> tuple[bool, str, str]:
    resolved = resolve_whatsapp_destination(
        record,
        to_phone=to_phone,
        allow_default_fallback=allow_default_fallback,
    )
    return resolved.is_valid, resolved.rejected_reason, resolved.normalized_phone


def _safe_dte_for_whatsapp(record: DTERecord) -> dict:
    request_payload = record.request_payload or {}
    if not isinstance(request_payload, dict):
        return {}
    dte = request_payload.get("dte")
    if not isinstance(dte, dict):
        return {}
    receptor = dte.get("receptor") if isinstance(dte.get("receptor"), dict) else {}
    direccion = receptor.get("direccion") if isinstance(receptor.get("direccion"), dict) else {}
    safe_receptor = {
        **receptor,
        "direccion": {
            "departamento": str(direccion.get("departamento") or "").strip(),
            "municipio": str(direccion.get("municipio") or "").strip(),
            "complemento": str(direccion.get("complemento") or "").strip(),
        },
    }
    return {**dte, "receptor": safe_receptor}


def build_whatsapp_payload(record: DTERecord, destination: WhatsAppDestinationResolution) -> dict:
    base = build_delivery_base_payload(record)
    invoice_json = base.get("invoice_json") if isinstance(base.get("invoice_json"), dict) else {}
    dte = _safe_dte_for_whatsapp(record) or (invoice_json.get("dte") if isinstance(invoice_json.get("dte"), dict) else {})
    receptor = dte.get("receptor") if isinstance(dte.get("receptor"), dict) else {}
    if not str(receptor.get("telefono") or "").strip():
        dte["receptor"] = {**receptor, "telefono": destination.normalized_phone}
    respuesta_hacienda = base.get("respuesta_hacienda") if isinstance(base.get("respuesta_hacienda"), dict) else {}
    tipo_dte = "01"
    doc_type = "CF"
    normalized = (record.dte_type or "").upper()
    if normalized.startswith("CCF"):
        tipo_dte, doc_type = "03", "CCF"
    elif normalized.startswith("SE"):
        tipo_dte, doc_type = "14", "SX"
    elif isinstance(dte.get("identificacion"), dict) and dte["identificacion"].get("tipoDte"):
        tipo_dte = str(dte["identificacion"]["tipoDte"])
    empresa_nombre = base.get("company_name") or resolve_delivery_config().whatsapp_company_name or "PicoPOS"
    resumen = dte.get("resumen") if isinstance(dte.get("resumen"), dict) else {}
    total = float(resumen.get("totalPagar") or base.get("total") or record.total_amount or 0)
    num_cliente = str(getattr(record.order, "whatsapp_num_cliente", "") or "").strip()
    return {
        "num_receptor": destination.normalized_phone,
        **({"num_cliente": num_cliente} if num_cliente else {}),
        "send_json": True,
        "dte": dte,
        "tipo_dte": tipo_dte,
        "doc_type": doc_type,
        "issued_id": base.get("issued_id"),
        "order_id": base.get("order_id"),
        "generation_code": base.get("generation_code"),
        "codigoGeneracion": base.get("generation_code"),
        "control_number": base.get("control_number"),
        "numeroControl": base.get("control_number"),
        "receiver_name": base.get("receiver_name"),
        "estado_mh": base.get("estado_mh"),
        "estadoMH": base.get("estado_mh"),
        "empresa": empresa_nombre,
        "empresa_nombre": empresa_nombre,
        "total": total,
        "invoice_json": {"dte": dte, "respuesta_hacienda": respuesta_hacienda},
        "descripcion_msg": f"DTE {record.control_number} estado {record.status}",
    }


def send_dte_whatsapp(record: DTERecord, to_phone: str | None = None) -> DteDeliveryAttempt:
    config = resolve_delivery_config()
    endpoint = config.whatsapp_url
    key = config.whatsapp_api_key

    attempt = DteDeliveryAttempt.objects.create(dte_record=record, delivery_type=DteDeliveryAttempt.TYPE_WA, status="PENDING", retries=0)
    provider_status = 0
    provider_body = {}
    error = ""
    destination = resolve_whatsapp_destination(record, to_phone=to_phone)

    if not destination.is_valid:
        attempt.status = "FAILED"
        attempt.provider_body = {
            "error": destination.rejected_reason,
            "provider_message": destination.rejected_reason,
            "to_phone": destination.normalized_phone or None,
            "destination_source": destination.source,
            "raw_phone_masked": _mask_phone(destination.raw_phone),
            "normalized_phone_masked": _mask_phone(destination.normalized_phone),
        }
        attempt.save(update_fields=["status", "provider_body", "retries"])
        logger.warning(
            "WHATSAPP_JOB_START job_id=%s destination_source=%s raw_phone=%s normalized_phone=%s error=%s",
            attempt.id,
            destination.source,
            _mask_phone(destination.raw_phone),
            _mask_phone(destination.normalized_phone),
            destination.rejected_reason,
        )
        return attempt

    payload = build_whatsapp_payload(record, destination)
    contract_missing = _validate_whatsapp_payload_contract(payload)
    if contract_missing:
        error = f"payload_missing_required:{','.join(contract_missing)}"
        attempt.status = "FAILED"
        attempt.provider_body = {
            "error": error,
            "provider_message": "Payload de WhatsApp incompleto; se cancela envío.",
            "request_payload": _sanitize_payload_for_log(payload),
            "missing_fields": contract_missing,
            "to_phone": destination.normalized_phone,
            "endpoint": endpoint,
        }
        attempt.save(update_fields=["status", "provider_body", "retries"])
        logger.error(
            "WHATSAPP_PAYLOAD_INVALID job_id=%s order_id=%s issued_id=%s missing=%s endpoint=%s",
            attempt.id,
            record.order_id,
            record.id,
            contract_missing,
            endpoint,
        )
        return attempt

    files, file_meta = _build_whatsapp_files(record, payload)
    has_pdf_attachment = any(item.get("field") == "pdf_file" for item in file_meta)
    if not has_pdf_attachment:
        error = "pdf_attachment_missing"
        attempt.status = "FAILED"
        attempt.provider_body = {
            "error": error,
            "provider_message": "No se pudo generar el PDF completo del DTE para WhatsApp.",
            "request_payload": _sanitize_payload_for_log(payload),
            "to_phone": destination.normalized_phone,
            "destination_source": destination.source,
            "endpoint": endpoint,
            "attachments": file_meta,
        }
        attempt.save(update_fields=["status", "provider_body", "retries"])
        logger.error(
            "WHATSAPP_ATTACHMENTS_INVALID job_id=%s order_id=%s issued_id=%s reason=%s attachments=%s",
            attempt.id,
            record.order_id,
            record.id,
            error,
            file_meta,
        )
        return attempt

    form_data = _build_whatsapp_form_data(payload)
    request_headers = {"X-API-Key": key}
    logger.info(
        "WHATSAPP_JOB_START job_id=%s order_id=%s issued_id=%s channel=whatsapp destination_source=%s destination=%s endpoint=%s has_num_receptor=%s has_num_cliente=%s num_cliente=%s num_receptor_intacto=%s has_dte=%s has_respuesta_hacienda=%s has_pdf=%s has_json=%s tipo_dte=%s gen=%s control=%s has_sello=%s has_fh=%s attachment_meta=%s",
        attempt.id,
        record.order_id,
        record.id,
        destination.source,
        _mask_phone(destination.normalized_phone),
        endpoint,
        bool(payload.get("num_receptor")),
        bool(payload.get("num_cliente")),
        _mask_phone(payload.get("num_cliente")),
        bool(payload.get("num_receptor") == destination.normalized_phone),
        isinstance(payload.get("dte"), dict) and bool(payload.get("dte")),
        isinstance((payload.get("invoice_json") or {}).get("respuesta_hacienda"), dict),
        True,
        bool(payload.get("send_json")),
        payload.get("tipo_dte"),
        payload.get("generation_code"),
        payload.get("control_number"),
        bool(((payload.get("invoice_json") or {}).get("respuesta_hacienda") or {}).get("selloRecibido") or ((payload.get("invoice_json") or {}).get("respuesta_hacienda") or {}).get("sello_recibido")),
        bool(((payload.get("invoice_json") or {}).get("respuesta_hacienda") or {}).get("fhProcesamiento") or ((payload.get("invoice_json") or {}).get("respuesta_hacienda") or {}).get("fh_procesamiento")),
        file_meta,
    )
    _log_whatsapp_request_debug(
        attempt=attempt,
        endpoint=endpoint,
        headers=request_headers,
        payload=payload,
        file_meta=file_meta,
        data=form_data,
        as_multipart=True,
    )

    for retry in range(3):
        attempt.retries = retry + 1
        if not endpoint:
            error = "WHATSAPP_DTE_API_BASE missing"
            break
        try:
            response = requests.post(
                endpoint,
                data=form_data,
                files=files,
                headers=request_headers,
                timeout=8,
            )
            provider_status = response.status_code
            provider_body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text[:3000]}
            _log_whatsapp_response_debug(attempt=attempt, response=response, provider_body=provider_body)
            logger.info(
                "WHATSAPP_PROVIDER_RESPONSE job_id=%s delivery_type=%s destination=%s status=%s body=%s",
                attempt.id,
                "multipart_bundle",
                _mask_phone(destination.normalized_phone),
                response.status_code,
                str(provider_body)[:800],
            )
            if 200 <= response.status_code < 300:
                if not _response_has_job_signal(provider_body or {}, response.status_code):
                    error = "provider_2xx_without_job_signal"
                    logger.warning(
                        "WHATSAPP_PROVIDER_UNCONFIRMED_ENQUEUE job_id=%s retry=%s body=%s",
                        attempt.id,
                        retry + 1,
                        _json_compact(provider_body or {}),
                    )
                    continue
                provider_status_text = str((provider_body or {}).get("status") or "").strip().lower()
                is_queued = bool((provider_body or {}).get("queued")) or provider_status_text == "queued"
                attempt.status = "QUEUED" if is_queued else "SENT"
                break
            error = f"http_{response.status_code}"
            logger.warning(
                "WHATSAPP_PROVIDER_ERROR job_id=%s destination=%s status=%s provider_message=%s",
                attempt.id,
                _mask_phone(destination.normalized_phone),
                response.status_code,
                str((provider_body or {}).get("message") or (provider_body or {}).get("detail") or "")[:600],
            )
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            logger.warning(
                "WHATSAPP_PROVIDER_EXCEPTION job_id=%s destination=%s error=%s",
                attempt.id,
                _mask_phone(destination.normalized_phone),
                error,
            )
        time.sleep(1)

    if attempt.status not in {"SENT", "QUEUED"}:
        attempt.status = "FAILED"
    attempt.provider_status = provider_status or None
    provider_status_text = str((provider_body or {}).get("status") or "").strip().lower()
    queued = attempt.status == "QUEUED" or bool((provider_body or {}).get("queued")) or provider_status_text == "queued"
    provider_message = str(
        (provider_body or {}).get("message")
        or (provider_body or {}).get("detail")
        or ("Job encolado para envío por WhatsApp" if queued else error)
        or ""
    ).strip()
    attempt.provider_body = {
        **(provider_body or {}),
        "error": error or None,
        "provider_message": provider_message or None,
        "request_payload": payload,
        "to_phone": destination.normalized_phone,
        "destination_source": destination.source,
        "raw_phone_masked": _mask_phone(destination.raw_phone),
        "normalized_phone_masked": _mask_phone(destination.normalized_phone),
        "endpoint": endpoint,
        "queued": queued,
        "job_id": (provider_body or {}).get("job_id"),
        "attachments": file_meta,
    }
    attempt.save(update_fields=["status", "provider_status", "provider_body", "retries"])
    logger.info(
        "WHATSAPP_JOB_FINISH job_id=%s status=%s destination_source=%s destination=%s provider_status=%s error=%s",
        attempt.id,
        attempt.status,
        destination.source,
        _mask_phone(destination.normalized_phone),
        provider_status,
        error,
    )
    return attempt
