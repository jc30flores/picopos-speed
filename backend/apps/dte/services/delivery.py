from __future__ import annotations

from collections.abc import Iterable

from apps.core.audit import log_audit
from apps.dte.models import DTERecord
from apps.dte.services.availability import evaluate_record_actions
from apps.dte.services.email_dte_service import send_dte_email
from apps.dte.services.whatsapp_dte_service import send_dte_whatsapp


def _normalize_channels(channels: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for channel in channels or []:
        normalized = str(channel or "").strip().lower()
        if normalized in {"email", "whatsapp"} and normalized not in out:
            out.append(normalized)
    return out


def _channel_result(*, ok: bool, status_code: int | None = None, error: str | None = None) -> dict:
    return {
        "ok": bool(ok),
        "status_code": status_code if isinstance(status_code, int) else None,
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
) -> dict:
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
    results: dict[str, dict] = {}

    for channel in selected_channels:
        if channel == "email":
            if not flags.get("can_send_email"):
                results[channel] = _channel_result(ok=False, error=flags.get("missing_email_reason") or "Cliente sin correo")
            else:
                attempt = send_dte_email(target, to_email=to_email or flags.get("customer_email"))
                provider_error = str((attempt.provider_body or {}).get("error") or "").strip()
                results[channel] = _channel_result(
                    ok=attempt.status == "SENT",
                    status_code=attempt.provider_status,
                    error=provider_error or ("No se pudo enviar correo" if attempt.status != "SENT" else None),
                )
        if channel == "whatsapp":
            if not flags.get("can_send_whatsapp"):
                results[channel] = _channel_result(ok=False, error=flags.get("missing_phone_reason") or "Cliente sin teléfono")
            else:
                attempt = send_dte_whatsapp(target, to_phone=to_phone or flags.get("customer_phone"))
                provider_error = str((attempt.provider_body or {}).get("error") or "").strip()
                results[channel] = _channel_result(
                    ok=attempt.status == "SENT",
                    status_code=attempt.provider_status,
                    error=provider_error or ("No se pudo enviar WhatsApp" if attempt.status != "SENT" else None),
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
    }
