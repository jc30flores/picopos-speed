from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTEBranchConfig, DTEControlCounter
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
        cfg = DTEBranchConfig.objects.filter(branch=order.branch, is_active=True).first()
        est_code = (cfg.cod_estable if cfg and cfg.cod_estable else "M001")
        pv_code = (cfg.cod_punto_venta if cfg and cfg.cod_punto_venta else "P001")
        counter, _ = DTEControlCounter.objects.select_for_update().get_or_create(
            branch=order.branch,
            dte_type=dte_type,
            tipo_dte=dte_type,
            year=now.year,
            anio_emision=now.year,
            establishment_code=est_code,
            est_code=est_code,
            pos_code=pv_code,
            pv_code=pv_code,
            ambiente=ambiente,
            defaults={"last_number": 0},
        )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])

    tipo = DOC_CODE_BY_TYPE.get(dte_type, "00")
    est_pv = f"{counter.establishment_code}{counter.pos_code}"
    return f"DTE-{tipo}-{est_pv}-{counter.last_number:015d}"
