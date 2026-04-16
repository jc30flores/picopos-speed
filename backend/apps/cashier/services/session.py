from __future__ import annotations

from apps.cashier.models import CashSession, Register
from apps.core.models import Branch


def resolve_branch_id(raw_branch_id=None, *, fallback_to_default: bool = False) -> int | None:
    if raw_branch_id is not None and str(raw_branch_id).isdigit():
        return int(raw_branch_id)
    if not fallback_to_default:
        return None
    principal = Branch.objects.filter(code="PRINCIPAL", is_active=True).first()
    if principal:
        return principal.id
    first = Branch.objects.filter(is_active=True).order_by("id").first()
    return first.id if first else None


def get_open_cash_session_for_branch(branch_id: int | None) -> CashSession | None:
    # closed_at is the canonical "open" marker. status can become stale in legacy rows.
    queryset = CashSession.objects.filter(closed_at__isnull=True).select_related("register", "register__branch")
    if branch_id:
        queryset = queryset.filter(register__branch_id=branch_id)
    return queryset.order_by("-opened_at").first()


def resolve_open_cash_session(*, branch_id: int | None = None, session_id: int | None = None) -> tuple[CashSession | None, str | None]:
    """Resolve canonical open session for cashier flows.

    Resolution order:
    1) If session_id is provided, it must point to an open session and match branch_id when provided.
    2) Otherwise resolve by branch scope (or global when branch_id is omitted).
    """

    if session_id:
        session = (
            CashSession.objects.filter(id=session_id, closed_at__isnull=True)
            .select_related("register", "register__branch")
            .first()
        )
        if not session:
            return None, "SESSION_NOT_OPEN"
        if branch_id and session.register.branch_id != branch_id:
            return None, "SESSION_BRANCH_MISMATCH"
        return session, None

    return get_open_cash_session_for_branch(branch_id), None


def has_open_cash_session_for_branch(branch_id: int | None) -> bool:
    if not branch_id:
        return CashSession.objects.filter(closed_at__isnull=True).exists()
    if not Register.objects.filter(branch_id=branch_id, is_active=True).exists():
        return True
    return CashSession.objects.filter(register__branch_id=branch_id, closed_at__isnull=True).exists()
