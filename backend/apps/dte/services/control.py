from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTEControlCounter
from apps.orders.models import Order


def build_generation_code(current: str | None = None) -> str:
    return (current or str(uuid.uuid4())).upper()


def next_control_number(order: Order, doc_type: str = "CF", environment: str = "test") -> str:
    now = timezone.localtime()
    with transaction.atomic():
        counter, _ = DTEControlCounter.objects.select_for_update().get_or_create(
            branch=order.branch,
            dte_type=doc_type,
            year=now.year,
            establishment_code="001",
            pos_code="001",
            ambiente=environment,
            defaults={"last_number": 0},
        )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])
    return f"{doc_type}-{order.branch.code}-{now.year}-{counter.last_number:015d}"
