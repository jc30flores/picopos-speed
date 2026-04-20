from __future__ import annotations

from datetime import timedelta
import re
from django.utils import timezone

from apps.dte.models import DTERecord
from apps.dte.services.delivery_config import INTERNAL_BILLING_EMAIL, resolve_delivery_config


def resolve_issued_at(record: DTERecord):
    return record.recibido_at or record.last_sent_at or record.created_at


def _format_remaining(delta) -> str:
    total_seconds = int(max(delta.total_seconds(), 0))
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def evaluate_record_actions(record: DTERecord) -> dict:
    now = timezone.now()
    issued_at = resolve_issued_at(record)
    dte_type = (record.dte_type or "").upper()

    can_resend = record.status == DTERecord.STATUS_PENDING

    credit_note_reason = ""
    has_credit_note = record.credit_notes.exists()
    can_credit_note = True
    if not dte_type.startswith("CCF"):
        can_credit_note = False
        credit_note_reason = "Solo aplica para CCF"
    elif record.status != DTERecord.STATUS_ACCEPTED:
        can_credit_note = False
        credit_note_reason = "Solo disponible cuando está aceptado"
    elif has_credit_note:
        can_credit_note = False
        credit_note_reason = "Ya existe nota de crédito"

    invalidate_reason = ""
    invalidate_deadline = None
    invalidate_remaining = ""
    can_invalidate = True
    if record.status != DTERecord.STATUS_ACCEPTED:
        can_invalidate = False
        invalidate_reason = "Solo aplica para DTE aceptado"
    else:
        if dte_type.startswith("CCF"):
            invalidate_deadline = issued_at + timedelta(hours=24)
            if now > invalidate_deadline:
                can_invalidate = False
                invalidate_reason = "Fuera de ventana: >24h"
        elif dte_type.startswith("CF") or dte_type.startswith("SE"):
            invalidate_deadline = issued_at + timedelta(days=90)
            if now > invalidate_deadline:
                can_invalidate = False
                invalidate_reason = "Fuera de ventana: >90 días"
        else:
            can_invalidate = False
            invalidate_reason = "Tipo no soportado para invalidación"

        if can_invalidate and invalidate_deadline:
            invalidate_remaining = _format_remaining(invalidate_deadline - now)

    customer = getattr(record.order, "customer", None)
    email = ((getattr(customer, "correo", "") or getattr(customer, "email", "") or "").strip() if customer else "")
    phone = ((getattr(customer, "telefono", "") or "").strip() if customer else "")
    phone_override = (getattr(record.order, "whatsapp_num_cliente", "") or "").strip()
    config = resolve_delivery_config()
    fallback_phone = (config.whatsapp_default_phone or "").strip() if config.whatsapp_allow_default_fallback else ""
    email_ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email or ""))
    email_is_internal = email.lower() == INTERNAL_BILLING_EMAIL.lower() if email else False

    can_send_email = bool(email and email_ok and not email_is_internal)
    can_send_whatsapp = bool(phone_override or phone or fallback_phone)
    missing_email_reason = ""
    if not can_send_email:
        if not email:
            missing_email_reason = "Cliente sin correo"
        elif not email_ok:
            missing_email_reason = "Correo de cliente inválido"
        elif email_is_internal:
            missing_email_reason = "Correo interno no permitido para envío automático"
        else:
            missing_email_reason = "Correo no disponible"
    missing_phone_reason = "" if can_send_whatsapp else "Cliente sin teléfono"

    return {
        "issued_at": issued_at,
        "can_resend": can_resend,
        "can_send_email": can_send_email,
        "missing_email_reason": missing_email_reason,
        "can_send_whatsapp": can_send_whatsapp,
        "missing_phone_reason": missing_phone_reason,
        "can_credit_note": can_credit_note,
        "credit_note_reason": credit_note_reason,
        "has_credit_note": has_credit_note,
        "can_invalidate": can_invalidate,
        "invalidate_reason": invalidate_reason,
        "invalidate_deadline": invalidate_deadline,
        "invalidate_remaining": invalidate_remaining,
        "customer_email": email,
        "customer_phone": phone,
        "customer_phone_override": phone_override,
    }
