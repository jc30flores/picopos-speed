from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def q2(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents(value: Decimal | int | float | str | None) -> int:
    return int((q2(Decimal(str(value if value is not None else "0"))) * 100).to_integral_value(rounding=ROUND_HALF_UP))


def from_cents(value: int | None) -> Decimal:
    return q2(Decimal(int(value or 0)) / 100)
