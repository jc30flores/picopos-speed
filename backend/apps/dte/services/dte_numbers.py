from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTEControlCounter
from apps.orders.models import Order


def next_control_number(order: Order, dte_type: str = "CF", ambiente: str = "test") -> str:
    now = timezone.localtime()
    year = now.year
    with transaction.atomic():
        counter, _ = DTEControlCounter.objects.select_for_update().get_or_create(
            branch=order.branch,
            ambiente=ambiente,
            dte_type=dte_type,
            year=year,
            establishment_code="001",
            pos_code="001",
            defaults={"last_number": 0},
        )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])
        number = f"{counter.last_number:015d}"
    return f"{dte_type}-{order.branch.code}-{year}-{number}"
