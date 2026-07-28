from __future__ import annotations

from datetime import datetime, time

from django.utils import timezone
from django.utils.dateparse import parse_date


def get_business_local_datetime(value: datetime | None = None) -> datetime:
    current = value or timezone.now()
    tz = timezone.get_current_timezone()
    if timezone.is_naive(current):
        current = timezone.make_aware(current, tz)
    return timezone.localtime(current, tz)


def parse_business_date_range(date_from_raw: str | None, date_to_raw: str | None) -> tuple[datetime | None, datetime | None]:
    date_from = parse_date(date_from_raw or "")
    date_to = parse_date(date_to_raw or "")
    tz = timezone.get_current_timezone()

    start = timezone.make_aware(datetime.combine(date_from, time.min), tz) if date_from else None
    end = timezone.make_aware(datetime.combine(date_to, time.max), tz) if date_to else None
    return start, end
