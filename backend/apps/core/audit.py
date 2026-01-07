from typing import Any
from django.http import HttpRequest
from apps.core.models import AuditLog


def get_client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_audit(
    request: HttpRequest,
    action: str,
    entity_type: str,
    entity_id: str | int,
    metadata: dict[str, Any] | None = None,
) -> None:
    user = request.user if request.user.is_authenticated else None
    AuditLog.objects.create(
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
        ip_address=get_client_ip(request),
    )
