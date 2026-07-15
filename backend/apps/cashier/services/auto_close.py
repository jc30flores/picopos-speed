from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.utils import timezone

from apps.cashier.models import CashSession
from apps.cashier.serializers import calculate_shift_summary
from apps.core.models import AuditLog, BusinessHoursSettings
from apps.orders.models import Order

logger = logging.getLogger(__name__)


AUTO_CLOSE_NOTE = "Cierre automático por horario de atención. Conteo registrado en 0 por cierre olvidado."
AUTO_CLOSE_SKIPPED_OPEN_ORDERS = "Cierre automático omitido: existen cuentas abiertas."


def count_open_orders_for_cash_close(branch_id: int | None) -> int:
    queryset = (
        Order.objects.filter(
            is_pending=True,
            items__isnull=False,
            total__gt=Decimal("0.00"),
            amount_due_cents__gt=0,
        )
        .exclude(status__in=["canceled", "delivered"])
        .exclude(payment_status="paid")
        .exclude(financial_status__in=["paid", "voided", "refunded_full"])
        .distinct()
    )
    if branch_id:
        queryset = queryset.filter(branch_id=branch_id)
    return queryset.count()


def _json_safe(value):
    return json.loads(json.dumps(value, default=str))


def _settings_timezone(settings: BusinessHoursSettings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.timezone or "America/El_Salvador")
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/El_Salvador")


def _closing_deadline_for_session(session: CashSession, settings: BusinessHoursSettings, tz: ZoneInfo):
    opened_local = timezone.localtime(session.opened_at, tz)
    business_date = opened_local.date()
    closes_next_day = settings.closing_time <= settings.opening_time
    if closes_next_day and opened_local.time() < settings.closing_time:
        business_date = business_date - timedelta(days=1)
    elif not closes_next_day and opened_local.time() < settings.opening_time:
        business_date = business_date - timedelta(days=1)

    close_date = business_date + (timedelta(days=1) if closes_next_day else timedelta())
    close_at = datetime.combine(close_date, settings.closing_time, tzinfo=tz)
    deadline = close_at + timedelta(hours=int(settings.grace_hours_after_close or 0))
    if opened_local > deadline:
        business_date = opened_local.date()
        close_date = business_date + (timedelta(days=1) if closes_next_day else timedelta())
        close_at = datetime.combine(close_date, settings.closing_time, tzinfo=tz)
        deadline = close_at + timedelta(hours=int(settings.grace_hours_after_close or 0))
    return close_at, deadline


def maybe_auto_close_expired_cash_sessions(now=None) -> dict:
    settings, _ = BusinessHoursSettings.objects.get_or_create(pk=1)
    if not settings.business_hours_enabled or not settings.auto_close_cash_enabled:
        return {"closed": 0, "skipped": 0, "details": []}

    tz = _settings_timezone(settings)
    now_value = now or timezone.now()
    if timezone.is_naive(now_value):
        now_value = timezone.make_aware(now_value, datetime_timezone.utc)
    now_local = timezone.localtime(now_value, tz)
    session_ids = list(
        CashSession.objects.filter(status="open", closed_at__isnull=True).values_list("id", flat=True)
    )
    result = {"closed": 0, "skipped": 0, "details": []}
    zero = Decimal("0.00")

    for session_id in session_ids:
        with transaction.atomic():
            session = (
                CashSession.objects.select_for_update()
                .select_related("register", "register__branch")
                .filter(id=session_id, status="open", closed_at__isnull=True)
                .first()
            )
            if not session:
                continue
            close_at, deadline = _closing_deadline_for_session(session, settings, tz)
            if now_local < deadline:
                continue
            pending_count = count_open_orders_for_cash_close(session.register.branch_id)
            if pending_count:
                logger.warning(
                    "cash_session.auto_close.skipped session_id=%s branch_id=%s pending_orders=%s reason=%s",
                    session.id,
                    session.register.branch_id,
                    pending_count,
                    AUTO_CLOSE_SKIPPED_OPEN_ORDERS,
                )
                result["skipped"] += 1
                result["details"].append(
                    {
                        "session_id": session.id,
                        "closed": False,
                        "pending_orders": pending_count,
                        "message": AUTO_CLOSE_SKIPPED_OPEN_ORDERS,
                    }
                )
                continue

            session.status = "closed"
            session.closed_by = None
            session.closed_at = now_value
            session.closing_counted_cash = zero
            session.closing_total_bills = zero
            session.closing_total_coins = zero
            session.closing_total_pos_cards = zero
            session.closing_total_pedidos_ya = zero
            session.close_type = CashSession.CLOSE_TYPE_AUTOMATIC_AFTER_HOURS
            session.notes = f"{session.notes}\n{AUTO_CLOSE_NOTE}".strip()
            snapshot = calculate_shift_summary(session)
            session.summary_snapshot = _json_safe(snapshot)
            session.save(
                update_fields=[
                    "status",
                    "closed_by",
                    "closed_at",
                    "closing_counted_cash",
                    "closing_total_bills",
                    "closing_total_coins",
                    "closing_total_pos_cards",
                    "closing_total_pedidos_ya",
                    "close_type",
                    "notes",
                    "summary_snapshot",
                ]
            )
            AuditLog.objects.create(
                action="cash_session.auto_close",
                entity_type="CashSession",
                entity_id=str(session.id),
                metadata={
                    "register_id": session.register_id,
                    "branch_id": session.register.branch_id,
                    "closed_at": now_value.isoformat(),
                    "scheduled_close_at": close_at.isoformat(),
                    "deadline": deadline.isoformat(),
                    "notes": AUTO_CLOSE_NOTE,
                },
            )
            logger.info("cash_session.auto_close.closed session_id=%s branch_id=%s", session.id, session.register.branch_id)
            result["closed"] += 1
            result["details"].append(
                {
                    "session_id": session.id,
                    "closed": True,
                    "pending_orders": 0,
                    "message": AUTO_CLOSE_NOTE,
                }
            )
    return result
