from __future__ import annotations

from collections.abc import Iterable

from apps.core.audit import log_audit
from apps.dte.models import DTERecord
from apps.dte.services.availability import evaluate_record_actions
from apps.dte.services.delivery_config import resolve_delivery_config
from apps.dte.services.email_dte_service import send_dte_email, validate_delivery_email_target
from apps.dte.services.whatsapp_dte_service import send_dte_whatsapp, validate_whatsapp_target


def _normalize_channels(channels: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for channel in channels or []:
        normalized = str(channel or "").strip().lower()
        if normalized in {"email", "whatsapp"} and normalized not in out:
            out.append(normalized)
    return out


def _channel_result(
    *,
    ok: bool,
    status_code: int | None = None,
    error: str | None = None,
    provider_status: int | None = None,
    provider_message: str | None = None,
    recipient: str | None = None,
) -> dict:
    return {
        "ok": bool(ok),
        "status_code": status_code if isinstance(status_code, int) else None,
        "provider_status": provider_status if isinstance(provider_status, int) else None,
        "provider_message": provider_message or None,
        "recipient": recipient or None,
        "error": error or None,
    }


def deliver_dte_to_client(
    target: DTERecord,
    *,
    channels: Iterable[str] = ("email", "whatsapp"),
    actor_user=None,
    request=None,
    to_email: str | None = None,
    to_phone: str | None = None,
    mode: str = "manual",
) -> dict:
    if target.status != DTERecord.STATUS_ACCEPTED:
        return {
            "success": False,
            "order_id": target.order_id,
            "issued_id": target.id,
            "results": {},
            "summary": "Solo se permite delivery para DTE aceptado",
        }
    selected_channels = _normalize_channels(channels)
    if not selected_channels:
        return {
            "success": False,
            "order_id": target.order_id,
            "issued_id": target.id,
            "results": {},
            "summary": "Debe enviar channels con al menos uno: whatsapp, email",
        }

    flags = evaluate_record_actions(target)
    config = resolve_delivery_config()
    import logging
    logger = logging.getLogger("apps.dte")
    logger.info(
        "[DTE DELIVERY] mode=%s dte_id=%s email_url=%s whatsapp_url=%s has_email_key=%s has_wa_key=%s",
        mode,
        target.id,
        config.email_url,
        config.whatsapp_url,
        bool(config.email_api_key),
        bool(config.whatsapp_api_key),
    )
    results: dict[str, dict] = {}

    for channel in selected_channels:
        if channel == "email":
            ok_target, target_error, target_email = validate_delivery_email_target(target, to_email=to_email or flags.get("customer_email"))
            if not ok_target:
                results[channel] = _channel_result(
                    ok=False,
                    error=target_error or "Cliente sin correo",
                    provider_message=target_error or None,
                    recipient=target_email or None,
                )
            else:
                attempt = send_dte_email(target, to_email=target_email)
                provider_error = str((attempt.provider_body or {}).get("error") or "").strip()
                provider_message = str((attempt.provider_body or {}).get("provider_message") or "").strip()
                results[channel] = _channel_result(
                    ok=attempt.status == "SENT",
                    status_code=attempt.provider_status,
                    provider_status=attempt.provider_status,
                    provider_message=provider_message or None,
                    recipient=str((attempt.provider_body or {}).get("to_email") or target_email or "").strip() or None,
                    error=provider_error or ("No se pudo enviar correo" if attempt.status != "SENT" else None),
                )
        if channel == "whatsapp":
            ok_phone, phone_error, target_phone = validate_whatsapp_target(target, to_phone=to_phone or flags.get("customer_phone"))
            if not ok_phone:
                results[channel] = _channel_result(
                    ok=False,
                    error=phone_error or flags.get("missing_phone_reason") or "Cliente sin teléfono",
                    provider_message=phone_error or None,
                    recipient=target_phone or None,
                )
            else:
                attempt = send_dte_whatsapp(target, to_phone=target_phone)
                provider_error = str((attempt.provider_body or {}).get("error") or "").strip()
                provider_message = str((attempt.provider_body or {}).get("provider_message") or "").strip()
                queued = bool((attempt.provider_body or {}).get("queued"))
                results[channel] = _channel_result(
                    ok=attempt.status in {"SENT", "QUEUED"},
                    status_code=attempt.provider_status,
                    provider_status=attempt.provider_status,
                    provider_message=provider_message or ("Encolado para envío por WhatsApp" if queued else None),
                    recipient=str((attempt.provider_body or {}).get("to_phone") or target_phone or "").strip() or None,
                    error=provider_error or ("No se pudo enviar WhatsApp" if attempt.status not in {"SENT", "QUEUED"} else None),
                )

    success = bool(results) and all(bool(item.get("ok")) for item in results.values())
    if success:
        summary = "Envío completado por todos los canales solicitados."
    else:
        failed = ", ".join(channel for channel, item in results.items() if not item.get("ok"))
        summary = f"Fallo en canal(es): {failed}" if failed else "Uno o más envíos fallaron."

    if request is not None:
        for channel, channel_result in results.items():
            log_audit(
                request,
                f"dte.deliver.{channel}",
                "DTERecord",
                target.id,
                {
                    "order_id": target.order_id,
                    "issued_id": target.id,
                    "actor_user_id": getattr(actor_user, "id", None),
                    "status": "ok" if channel_result.get("ok") else "failed",
                    "status_code": channel_result.get("status_code"),
                    "error": channel_result.get("error"),
                },
            )

    return {
        "success": success,
        "order_id": target.order_id,
        "issued_id": target.id,
        "results": results,
        "summary": summary,
        "mode": mode,
    }
