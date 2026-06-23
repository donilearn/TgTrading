import re

from ai.short_price_resolver import resolve_short_price

_BUY_SELL_LINE = re.compile(r"\b(buy|sell)\b", re.IGNORECASE)
_ZONE_PAIR = re.compile(r"(\d+(?:\.\d+)?)\D{1,5}(\d+(?:\.\d+)?)")


def parse_zone_bounds(
    text: str | None,
    reference_price: float | None = None,
) -> tuple[float, float] | None:
    """Xabardan zone min/max ni ajratadi (masalan BUY 4105🛍4102)."""
    if not text:
        return None

    for line in text.splitlines():
        if not _BUY_SELL_LINE.search(line):
            continue

        match = _ZONE_PAIR.search(line)
        if not match:
            continue

        first = float(match.group(1))
        second = float(match.group(2))
        first = resolve_short_price(first, reference_price)
        second = resolve_short_price(second, reference_price)

        if first == second:
            continue

        return min(first, second), max(first, second)

    return None
