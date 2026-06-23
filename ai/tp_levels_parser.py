import re

from ai.short_price_resolver import resolve_short_price

_SUPERSCRIPT_LEVELS = {"¹": 1, "²": 2, "³": 3, "⁴": 4, "⁵": 5}
_TP_SUPER = re.compile(r"TP\s*([¹²³⁴⁵])\s*:?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_TP_NUM = re.compile(r"TP\s*([1-5])\s*:?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_tp_levels(
    text: str | None,
    reference_price: float | None = None,
) -> list[float]:
    """Xabardan TP¹..TP⁵ levellarini tartib bilan qaytaradi."""
    if not text:
        return []

    indexed: dict[int, float] = {}

    for match in _TP_SUPER.finditer(text):
        level = _SUPERSCRIPT_LEVELS[match.group(1)]
        price = resolve_short_price(float(match.group(2)), reference_price)
        indexed[level] = price

    for match in _TP_NUM.finditer(text):
        level = int(match.group(1))
        price = resolve_short_price(float(match.group(2)), reference_price)
        indexed[level] = price

    if not indexed:
        return []

    return [indexed[level] for level in sorted(indexed)]
