from __future__ import annotations

import uuid
from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTEBranchConfig, DTEControlCounter
from apps.orders.models import Order


class DTEBranchResolutionError(Exception):
    pass


DOC_CODE_BY_TYPE = {
    "CF_01": "01",
    "CCF_03": "03",
    "SE_14": "14",
    "NC_05": "05",
    "INVALIDACION": "AN",
}


def build_generation_code(current: str | None = None) -> str:
    return (current or str(uuid.uuid4())).upper()


def reserve_next_control(
    *,
    branch,
    document_type: str,
    establishment_code: str,
    pos_code: str,
    ambiente: str = "00",
    year: int | None = None,
) -> str:
    now = timezone.localtime()
    year_value = int(year or now.year)
    establishment_code = (establishment_code or "").strip().upper()
    pos_code = (pos_code or "").strip().upper()
    if not establishment_code or not pos_code:
        raise DTEBranchResolutionError("cod_estable_mh/cod_punto_venta_mh son requeridos para reservar correlativo.")

    with transaction.atomic():
        counter = DTEControlCounter.objects.select_for_update().filter(
            branch=branch,
            dte_type=document_type,
            year=year_value,
            establishment_code=establishment_code,
            pos_code=pos_code,
            ambiente=ambiente,
        ).first()
        if not counter:
            raise DTEBranchResolutionError(
                f"No existe DTEControlCounter para branch_id={branch.id}, dte_type={document_type}, ambiente={ambiente}, "
                f"year={year_value}, establishment_code={establishment_code}, pos_code={pos_code}. "
                "Cree el registro en dte_dtecontrolcounter antes de enviar DTE."
            )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])
        last_number = counter.last_number

    tipo = DOC_CODE_BY_TYPE.get(document_type, "00")
    return f"DTE-{tipo}-{establishment_code}{pos_code}-{last_number:015d}"


def next_control_number(order: Order, dte_type: str = "CF_01", ambiente: str = "00") -> str:
    if not order.branch_id or not getattr(order, "branch", None):
        raise DTEBranchResolutionError(f"Order {order.id} no tiene branch asignado; no se puede generar numeroControl.")

    cfg = DTEBranchConfig.objects.filter(branch=order.branch, is_active=True).first()
    if not cfg:
        raise DTEBranchResolutionError(
            f"Order {order.id} branch_id={order.branch_id} no tiene DTEBranchConfig activa; no se permite fallback."
        )
    est_code = (cfg.cod_estable_mh or "").strip().upper()
    pv_code = (cfg.cod_punto_venta_mh or "").strip().upper()
    if not est_code or not pv_code:
        raise DTEBranchResolutionError(
            f"Order {order.id} branch_id={order.branch_id} tiene cod_estable_mh/cod_punto_venta_mh incompletos en DTEBranchConfig."
        )
    return reserve_next_control(
        branch=order.branch,
        document_type=dte_type,
        establishment_code=est_code,
        pos_code=pv_code,
        ambiente=ambiente,
    )
