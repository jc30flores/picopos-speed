from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTEControlCounter
from apps.orders.models import Order


DOC_CODE_BY_TYPE = {
    "CF_01": "01",
    "CCF_03": "03",
    "SE_14": "14",
    "NC_05": "05",
    "INVALIDACION": "AN",
}


def build_generation_code(current: str | None = None) -> str:
    return (current or str(uuid.uuid4())).upper()


def next_control_number(order: Order, dte_type: str = "CF_01", ambiente: str = "00") -> str:
    now = timezone.localtime()
    with transaction.atomic():
        counter, _ = DTEControlCounter.objects.select_for_update().get_or_create(
            branch=order.branch,
            dte_type=dte_type,
            year=now.year,
            establishment_code="001",
            pos_code="001",
            ambiente=ambiente,
            defaults={"last_number": 0},
        )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])

    tipo = DOC_CODE_BY_TYPE.get(dte_type, "00")
    est_pv = f"{counter.establishment_code}{counter.pos_code}"
    return f"DTE-{tipo}-{est_pv}-{counter.last_number:015d}"
