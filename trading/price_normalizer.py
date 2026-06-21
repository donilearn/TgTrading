import math
from typing import Any


def normalize_price(value: float | None, spec: dict) -> float | None:
    if value is None:
        return None

    tick = _float(spec.get("tickSize")) or _tick_from_digits(spec.get("digits"))
    digits = _int(spec.get("digits"))

    if tick and tick > 0:
        normalized = round(round(value / tick) * tick, 10)
    else:
        normalized = value

    if digits is not None:
        normalized = round(normalized, digits)

    return normalized


def _tick_from_digits(digits: Any) -> float | None:
    parsed = _int(digits)
    if parsed is None:
        return None
    return 10 ** (-parsed)


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
