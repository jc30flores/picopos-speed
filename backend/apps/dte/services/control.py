from __future__ import annotations

import uuid
import logging
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.dte.models import DTEBranchConfig, DTEControlCounter
from apps.orders.models import Order

logger = logging.getLogger("apps.dte")


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
    logger.info(
        "[DTE] counter_lookup branch_id=%s ambiente=%s dte_type=%s year=%s establishment_code=%s pos_code=%s",
        getattr(branch, "id", None),
        ambiente,
        document_type,
        year_value,
        establishment_code,
        pos_code,
    )

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
                "Cree el registro en dte_dtecontrolcounter antes de enviar DTE. "
                f"Ejemplo SQL: INSERT INTO dte_dtecontrolcounter (branch_id,dte_type,year,establishment_code,pos_code,ambiente,last_number,created_at,updated_at) "
                f"VALUES ({branch.id},'{document_type}',{year_value},'{establishment_code}','{pos_code}','{ambiente}',0,NOW(),NOW());"
            )
        counter.last_number += 1
        counter.save(update_fields=["last_number", "updated_at"])
        last_number = counter.last_number

    tipo = DOC_CODE_BY_TYPE.get(document_type, "00")
    return f"DTE-{tipo}-{establishment_code}{pos_code}-{last_number:015d}"


def next_control_number(order: Order, dte_type: str = "CF_01", ambiente: str = "00", branch=None) -> str:
    selected_branch = branch or getattr(order, "branch", None)
    selected_branch_id = getattr(selected_branch, "id", None)
    if not selected_branch_id or not selected_branch:
        raise DTEBranchResolutionError(f"Order {order.id} no tiene branch asignado; no se puede generar numeroControl.")

    cfg = DTEBranchConfig.objects.filter(branch=selected_branch, is_active=True).first()
    if not cfg:
        raise DTEBranchResolutionError(
            f"Order {order.id} branch_id={selected_branch_id} no tiene DTEBranchConfig activa; no se permite fallback."
        )
    env_est_code = (getattr(settings, "DTE_COD_ESTABLE_MH", "") or "").strip().upper()
    env_pv_code = (getattr(settings, "DTE_COD_PUNTO_VENTA_MH", "") or "").strip().upper()
    est_code = env_est_code or (cfg.cod_estable_mh or "").strip().upper()
    pv_code = env_pv_code or (cfg.cod_punto_venta_mh or "").strip().upper()
    if env_est_code and env_pv_code and env_est_code == env_pv_code:
        logger.warning(
            "[DTE] invalid_env_series env_establishment_code=%s env_pos_code=%s order=%s branch_id=%s",
            env_est_code,
            env_pv_code,
            order.id,
            selected_branch_id,
        )
        raise DTEBranchResolutionError(
            "Configuración inválida: DTE_COD_ESTABLE_MH y DTE_COD_PUNTO_VENTA_MH no pueden ser iguales."
        )
    if env_pv_code and not env_pv_code.startswith("P"):
        logger.warning("[DTE] suspicious_env_pos_code value=%s order=%s branch_id=%s", env_pv_code, order.id, selected_branch_id)
        raise DTEBranchResolutionError("Configuración inválida: DTE_COD_PUNTO_VENTA_MH debe iniciar con 'P' (ejemplo: P001).")
    if not est_code or not pv_code:
        raise DTEBranchResolutionError(
            f"Order {order.id} branch_id={selected_branch_id} tiene cod_estable_mh/cod_punto_venta_mh incompletos en DTEBranchConfig/env."
        )
    return reserve_next_control(
        branch=selected_branch,
        document_type=dte_type,
        establishment_code=est_code,
        pos_code=pv_code,
        ambiente=ambiente,
    )
