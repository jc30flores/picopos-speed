from __future__ import annotations

from apps.cashier.models import CashSession, Register
from apps.core.models import Branch


def resolve_branch_id(raw_branch_id=None) -> int | None:
    if raw_branch_id is not None and str(raw_branch_id).isdigit():
        return int(raw_branch_id)
    principal = Branch.objects.filter(code="PRINCIPAL", is_active=True).first()
    if principal:
        return principal.id
    first = Branch.objects.filter(is_active=True).order_by("id").first()
    return first.id if first else None


def get_open_cash_session_for_branch(branch_id: int | None) -> CashSession | None:
    if not branch_id:
        return None
    return (
        CashSession.objects.filter(register__branch_id=branch_id, status="open", closed_at__isnull=True)
        .select_related("register", "register__branch")
        .order_by("-opened_at")
        .first()
    )


def has_open_cash_session_for_branch(branch_id: int | None) -> bool:
    if not branch_id:
        return False
    if not Register.objects.filter(branch_id=branch_id, is_active=True).exists():
        return True
    return CashSession.objects.filter(register__branch_id=branch_id, status="open", closed_at__isnull=True).exists()

