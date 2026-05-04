from django.utils import timezone


def duration_seconds(start, end) -> int:
    if not start or not end:
        return 0
    return max(0, int((end - start).total_seconds()))


def sum_cycle_break_seconds(cycle, include_open=False, now=None) -> int:
    now = now or timezone.now()
    total = 0
    breaks = list(cycle.breaks.all()) if getattr(cycle, "pk", None) else []
    if breaks:
        for br in breaks:
            if br.end_at is None and not include_open:
                continue
            total += duration_seconds(br.start_at, br.end_at or now)
        return total
    if cycle.break_start_at:
        if cycle.break_end_at is None and not include_open:
            return 0
        return duration_seconds(cycle.break_start_at, cycle.break_end_at or now)
    return 0


def cycle_break_seconds_for_reports(cycle) -> int:
    if cycle.break_seconds_override is not None:
        return max(0, int(cycle.break_seconds_override))
    return sum_cycle_break_seconds(cycle, include_open=False)
