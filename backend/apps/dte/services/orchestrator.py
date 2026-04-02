from __future__ import annotations

import json
import logging
import os
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.models import Branch
from apps.dte.models import DTERecord
from apps.dte.outbox import send_or_queue_dte
from apps.dte.services.control import DTEBranchResolutionError, build_generation_code, next_control_number
from apps.dte.services.dte_service import (
    DTEPreflightError,
    build_payload_cf,
    interpret_dte_response,
)
from apps.orders.models import Order, OrderInvoice
from apps.orders.services.snapshots import persist_sale_snapshot

DTE_LOGGER = logging.getLogger("apps.dte")


def _normalize_ambiente(raw_value: str | None) -> str:
    value = (raw_value or "").strip().upper()
    if value == "01" or "01" in value or value in {"PROD", "PRODUCCION", "PRODUCTION"}:
        return "01"
    if value == "00" or "00" in value or value in {"TEST", "CERT", "CERTIFICACION", "DEV"}:
        return "00"
    return "01"


def _ambiente() -> str:
    raw = os.environ.get("DTE_AMBIENTE") or os.environ.get("MH_AMBIENTE") or os.environ.get("HACIENDA_AMBIENTE")
    return _normalize_ambiente(raw)


def _has_duplicate_control_error(invoice: OrderInvoice) -> bool:
    error_text = " ".join(
        [
            str(invoice.last_error or ""),
            str(invoice.last_dte_error or ""),
            str(invoice.last_dte_error_code or ""),
        ]
    ).upper()
    return "YA EXISTE UN REGISTRO CON ESE VALOR" in error_text or "NUMEROCONTROL" in error_text and "DUPLIC" in error_text


def _resolve_selected_branch(order: Order) -> Branch:
    env_branch_id = getattr(settings, "DTE_BRANCH_ID", None)
    if env_branch_id and int(env_branch_id) > 0:
        branch = Branch.objects.filter(id=int(env_branch_id)).first()
        if not branch:
            raise DTEPreflightError(f"DTE_BRANCH_ID={env_branch_id} no existe en core_branch.")
        return branch
    return order.branch


def transmit_sale_dte(
    sale_id: int,
    source: str = "normal_send",
    force: bool = False,
    payment_id: int | None = None,
    queue_only: bool = False,
) -> DTERecord:
    DTE_LOGGER.info("[DTE] send_dte.start order=%s payment=%s source=%s", sale_id, payment_id, source)
    order = Order.objects.select_related("branch", "service_type", "customer").prefetch_related("items__applied_modifiers", "payments__payment_method").get(pk=sale_id)
    if order.dte_document_type != "CF":
        DTE_LOGGER.info("[DTE] send_dte.skip order=%s reason=unsupported_doc_type type=%s", sale_id, order.dte_document_type)
        raise DTEPreflightError(f"Tipo DTE aún no implementado: {order.dte_document_type}")
    dte_type = "CF_01"

    accepted = DTERecord.objects.filter(order=order, dte_type=dte_type, status=DTERecord.STATUS_ACCEPTED).first()
    if accepted and not force:
        DTE_LOGGER.info("[DTE] send_dte.return_existing order=%s dte_record=%s", sale_id, accepted.id)
        return accepted

    invoice, _ = OrderInvoice.objects.get_or_create(order=order)
    ambiente = "01"
    codigo_generacion = build_generation_code(invoice.codigo_generacion)
    numero_control = invoice.numero_control or ""
    if numero_control and _has_duplicate_control_error(invoice):
        DTE_LOGGER.warning("[DTE] duplicate_control_detected order=%s old_numeroControl=%s -> reserving_new_control", sale_id, numero_control)
        numero_control = ""

    attempts = (invoice.dte_send_attempts or 0) + 1
    now = timezone.now()
    payment = order.payments.filter(id=payment_id).first() if payment_id else None
    env_branch_id = getattr(settings, "DTE_BRANCH_ID", None)
    selected_branch = _resolve_selected_branch(order)
    selected_branch_id = getattr(selected_branch, "id", None)
    payment_branch_id = None
    payment_register_id = getattr(getattr(payment, "cash_session", None), "register_id", None) if payment else None
    payment_register_branch_id = (
        getattr(getattr(getattr(payment, "cash_session", None), "register", None), "branch_id", None) if payment else None
    )
    user_profile_branch_id = None
    if payment and getattr(payment, "received_by", None):
        user_profile_branch_id = getattr(getattr(payment.received_by, "profile", None), "branch_id", None)
    DTE_LOGGER.info(
        "[DTE] branch_resolution order_id=%s order_branch_id=%s env_branch_id=%s payment_branch_id=%s payment_register_id=%s "
        "payment_register_branch_id=%s user_profile_branch_id=%s selected_branch_id=%s",
        order.id,
        order.branch_id,
        env_branch_id,
        payment_branch_id,
        payment_register_id,
        payment_register_branch_id,
        user_profile_branch_id,
        selected_branch_id,
    )
    if not selected_branch_id:
        raise DTEPreflightError(f"Order {order.id} no tiene branch asignado; no se permite fallback de DTE.")
    if (not env_branch_id or int(env_branch_id) <= 0) and selected_branch_id != order.branch_id:
        raise DTEPreflightError(
            f"Branch inconsistente para order {order.id}: order.branch_id={order.branch_id} selected_branch.id={selected_branch_id} env_branch_id={env_branch_id}"
        )

    payload: dict = {}
    prebuilt_record = DTERecord.objects.create(
        order=order,
        payment=payment,
        branch=selected_branch,
        dte_type=dte_type,
        status=DTERecord.STATUS_PENDING,
        ambiente=ambiente,
        control_number=numero_control,
        generation_code=codigo_generacion,
        codigo_generacion=codigo_generacion,
        request_payload={},
        response_payload={},
        response_text="",
        mh_response_json={},
        mh_response_text="",
        receiver_name=(order.customer.name if order.customer_id else order.customer_name) or "Consumidor Final",
        issue_date=timezone.localdate(),
        total_amount=order.total,
        source=source,
        attempts=attempts,
        send_attempts=attempts,
        last_sent_at=now,
    )

    try:
        preflight_control_number = numero_control or "PREFLIGHT-CHECK"
        build_payload_cf(order, control_number=preflight_control_number, generation_code=codigo_generacion, ambiente=ambiente)
        numero_control = numero_control or next_control_number(order, dte_type=dte_type, ambiente=ambiente, branch=selected_branch)
        DTE_LOGGER.info("Reservado correlativo CF: order=%s -> numeroControl=%s codigoGeneracion=%s", sale_id, numero_control, codigo_generacion)
        payload = build_payload_cf(order, control_number=numero_control, generation_code=codigo_generacion, ambiente=ambiente)
        emisor = ((payload or {}).get("dte") or {}).get("emisor") or {}
        DTE_LOGGER.info(
            "[DTE] control_context order_id=%s order_branch_id=%s dte_branch_id=%s cod_estable_mh=%s cod_punto_venta_mh=%s numeroControl=%s",
            order.id,
            order.branch_id,
            selected_branch_id,
            emisor.get("codEstableMH"),
            emisor.get("codPuntoVentaMH"),
            numero_control,
        )
        prebuilt_record.request_payload = {**payload, "branch": selected_branch.name}
        prebuilt_record.save(update_fields=["request_payload", "updated_at"])
    except (DTEPreflightError, DTEBranchResolutionError) as exc:
        DTE_LOGGER.info("[DTE] send_dte.preflight_failed order=%s error=%s", sale_id, exc)
        parsed = {
            "status": DTERecord.STATUS_REJECTED,
            "hacienda_uuid": "",
            "sello_recepcion": "",
            "sello_recibido": "",
            "firma": "",
            "recibido_at": None,
            "estado_mh": "",
            "hacienda_state": "PRECHECK",
            "error_code": "PRECHECK",
            "error_message": str(exc),
        }
        response = {"success": False, "error": {"message": str(exc)}}
    else:
        outbox = send_or_queue_dte(
            order=order,
            payment=payment,
            payload=payload,
            dte_record=prebuilt_record,
            attempt_immediate=not queue_only,
        )
        response = {}
        if outbox.response_body:
            try:
                response = json.loads(outbox.response_body)
            except Exception:
                response = {"raw": outbox.response_body}
        parsed = interpret_dte_response({**response, "http_status": outbox.response_status_code or 0, "response_text": outbox.response_body or ""})
        if outbox.status == "ACCEPTED":
            parsed["status"] = DTERecord.STATUS_ACCEPTED
        elif outbox.status == "REJECTED":
            parsed["status"] = DTERecord.STATUS_REJECTED
        elif outbox.status == "FAILED":
            parsed["status"] = DTERecord.STATUS_REJECTED
        elif outbox.status in {"PENDING", "SENT", "SENDING"}:
            parsed["status"] = DTERecord.STATUS_PENDING
        DTE_LOGGER.info(
            "[CF01] RECEIPT order=%s payment=%s estado=%s sello=%s firma=%s recibido_at=%s",
            sale_id,
            payment_id,
            parsed.get("estado_mh") or parsed.get("hacienda_state") or "",
            parsed.get("sello_recibido") or parsed.get("sello_recepcion") or "-",
            parsed.get("firma") or "-",
            parsed.get("recibido_at") or "-",
        )
    prebuilt_record.status = parsed["status"]
    prebuilt_record.request_payload = {**payload, "branch": selected_branch.name}
    prebuilt_record.response_payload = response if isinstance(response, dict) else {}
    prebuilt_record.response_text = parsed.get("response_text", "")
    prebuilt_record.mh_response_json = response if isinstance(response, dict) else {}
    prebuilt_record.mh_response_text = json.dumps(response, ensure_ascii=False, default=str) if isinstance(response, dict) else str(response)
    prebuilt_record.attempts = attempts
    prebuilt_record.send_attempts = attempts
    prebuilt_record.error_message = parsed["error_message"]
    prebuilt_record.error_code = parsed["error_code"]
    prebuilt_record.last_error_message = parsed["error_message"]
    prebuilt_record.last_error_code = parsed["error_code"]
    prebuilt_record.last_sent_at = now
    prebuilt_record.hacienda_uuid = parsed["hacienda_uuid"]
    prebuilt_record.sello_recepcion = parsed["sello_recepcion"]
    prebuilt_record.sello_recibido = parsed.get("sello_recibido", parsed["sello_recepcion"])
    prebuilt_record.firma = parsed.get("firma", "")
    prebuilt_record.recibido_at = parsed.get("recibido_at")
    prebuilt_record.estado_mh = parsed.get("estado_mh", "")
    prebuilt_record.hacienda_state = parsed["hacienda_state"]
    prebuilt_record.hacienda_processed_at = parsed.get("recibido_at")
    prebuilt_record.save()
    record = prebuilt_record

    invoice.status = "sent" if record.status == DTERecord.STATUS_ACCEPTED else "failed" if record.status == DTERecord.STATUS_REJECTED else "pending"
    invoice.dte_number = numero_control
    invoice.generation_code = codigo_generacion
    invoice.numero_control = numero_control
    invoice.codigo_generacion = codigo_generacion
    invoice.hacienda_payload = payload
    invoice.hacienda_response = response
    invoice.last_error = parsed["error_message"]
    invoice.dte_status = record.status
    invoice.dte_send_attempts = attempts
    invoice.last_dte_sent_at = now
    invoice.last_dte_error = parsed["error_message"]
    invoice.last_dte_error_code = parsed["error_code"]
    if record.status == DTERecord.STATUS_ACCEPTED:
        invoice.sent_at = now
    invoice.save()
    persist_sale_snapshot(order)
    DTE_LOGGER.info("[DTE] send_dte.done order=%s payment=%s record_status=%s", sale_id, payment_id, record.status)

    return record
