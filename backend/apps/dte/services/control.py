from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from apps.dte.services.active_branch import get_active_branch
from apps.dte.models import DTEControlCounter
from apps.dte.services.emisor import get_emisor_config
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


def reserve_next_control(*, branch, document_type: str, series: str = "X001X001", ambiente: str = "00", year: int | None = None) -> str:
    now = timezone.localtime()
    year_value = int(year or now.year)
    normalized_series = (series or "X001X001").upper()
    establishment_code = normalized_series[:4]
    pos_code = normalized_series[4:8]

    with transaction.atomic():
        counter, _ = DTEControlCounter.objects.select_for_update().get_or_create(
            branch=branch,
            dte_type=document_type,
            year=year_value,
            establishment_code=establishment_code,
            pos_code=pos_code,
            ambiente=ambiente,
            defaults={"last_number": 0},
        )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])
        last_number = counter.last_number

    tipo = DOC_CODE_BY_TYPE.get(document_type, "00")
    return f"DTE-{tipo}-{establishment_code}{pos_code}-{last_number:015d}"


def next_control_number(order: Order, dte_type: str = "CF_01", ambiente: str = "00") -> str:
    active_branch = get_active_branch()
    emisor_cfg = get_emisor_config()
    est_code = (emisor_cfg.get("codEstable") or "X001")
    pv_code = (emisor_cfg.get("codPuntoVenta") or "X001")
    return reserve_next_control(
        branch=active_branch,
        document_type=dte_type,
        series=f"{est_code}{pv_code}",
        ambiente=ambiente,
    )
