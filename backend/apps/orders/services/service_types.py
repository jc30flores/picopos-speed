from __future__ import annotations

from apps.core.models import ServiceType


def resolve_table_service_type() -> ServiceType | None:
    return (
        ServiceType.objects.filter(is_active=True, key__iexact="MESA").first()
        or ServiceType.objects.filter(is_active=True, label__iexact="Mesa").first()
    )
