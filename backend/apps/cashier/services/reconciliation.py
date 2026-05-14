from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.cashier.models import CashSession
from apps.payments.models import Payment, PaymentMethod, Refund
from apps.payments.normalization import normalize_payment_method_code, payment_code_from_payment

MONEY_Q = Decimal("0.01")


def _q2(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


@dataclass
class SessionMethodNet:
    totals_by_method: dict[str, Decimal]
    labels_by_method: dict[str, str]
    non_cash_movements: list[dict]


def _session_range(session: CashSession) -> tuple:
    start_at = session.opened_at
    end_at = session.closed_at or timezone.now()
    return start_at, end_at


def _payment_method_label_map() -> dict[str, str]:
    labels: dict[str, str] = {}
    for method in PaymentMethod.objects.all():
        code = normalize_payment_method_code(method.code)
        if not code:
            continue
        labels.setdefault(code, method.name or code.upper())
    labels.setdefault("cash", "Efectivo")
    labels.setdefault("card", "Tarjeta")
    labels.setdefault("transfer", "Transferencia")
    labels.setdefault("pedidos_ya", "Pedidos Ya")
    labels.setdefault("paypal", "PayPal")
    return labels


def _refund_method_code(refund: Refund) -> str:
    if refund.payment_method_id:
        fiscal_type = str(getattr(refund.payment_method, "fiscal_payment_type", "") or "").strip().upper()
        normalized = normalize_payment_method_code(refund.payment_method.code)
        if fiscal_type == "CASH":
            return "cash"
        if fiscal_type == "CARD":
            return normalized if normalized in {"pedidos_ya"} else "card"
        if fiscal_type == "TRANSFER":
            return normalized if normalized in {"paypal"} else "transfer"
        if normalized:
            return normalized
    return normalize_payment_method_code(refund.method or "") or "transfer"


def _payments_for_session_scope(session: CashSession):
    start_at, end_at = _session_range(session)
    base = Payment.objects.select_related("payment_method", "reporting_payment_method", "order")
    has_direct_session_rows = base.filter(cash_session=session).exists()
    if has_direct_session_rows:
        return base.filter(cash_session=session) | base.filter(
            cash_session__isnull=True,
            created_at__gte=start_at,
            created_at__lte=end_at,
        )
    return base.filter(created_at__gte=start_at, created_at__lte=end_at)


def _refunds_for_session_scope(session: CashSession):
    start_at, end_at = _session_range(session)
    base = Refund.objects.select_related("payment_method", "original_payment")
    has_direct_session_rows = base.filter(cash_session=session).exists()
    if has_direct_session_rows:
        return base.filter(cash_session=session) | base.filter(
            cash_session__isnull=True,
            created_at__gte=start_at,
            created_at__lte=end_at,
        )
    return base.filter(created_at__gte=start_at, created_at__lte=end_at)


def calculate_session_payment_method_net(session: CashSession) -> SessionMethodNet:
    labels_by_method = _payment_method_label_map()
    totals_by_method: dict[str, Decimal] = {code: Decimal("0") for code in labels_by_method}
    non_cash_movements: list[dict] = []

    for payment in _payments_for_session_scope(session):
        code = payment_code_from_payment(payment)
        gross = _q2((payment.amount or Decimal("0")) + (payment.tip_amount or Decimal("0")))
        totals_by_method[code] = _q2(totals_by_method.get(code, Decimal("0")) + gross)
        if code != "cash":
            non_cash_movements.append(
                {
                    "kind": "payment",
                    "payment_id": payment.id,
                    "order_id": payment.order_id,
                    "payment_method_code": code,
                    "amount": f"{gross:.2f}",
                    "created_at": payment.created_at.isoformat(),
                }
            )

    for refund in _refunds_for_session_scope(session):
        code = _refund_method_code(refund)
        refunded_total = _q2((refund.amount or Decimal("0")) + (refund.tip_refunded or Decimal("0")))
        totals_by_method[code] = _q2(totals_by_method.get(code, Decimal("0")) - refunded_total)
        if code != "cash":
            non_cash_movements.append(
                {
                    "kind": "refund",
                    "refund_id": refund.id,
                    "order_id": refund.order_id,
                    "payment_method_code": code,
                    "amount": f"{-refunded_total:.2f}",
                    "created_at": refund.created_at.isoformat(),
                }
            )

    return SessionMethodNet(
        totals_by_method={code: _q2(total) for code, total in totals_by_method.items()},
        labels_by_method=labels_by_method,
        non_cash_movements=sorted(non_cash_movements, key=lambda row: row.get("created_at", ""), reverse=True),
    )
